"""大模型客户端（方向 G）。

通过 OpenAI 兼容的 /chat/completions 协议调用大模型（DeepSeek 或任何兼容端点），
为刮削识别（G1）、观影报告（G3）、推荐精排（G2，阶段四）提供统一入口。

设计原则（见 docs/大数据增强方案-元数据本地化与热度信号.md 2.3 节）：
- 默认关闭、用户自配 Key；未启用/未配置时 is_ready() 为 False，业务方直接走规则逻辑；
- 所有异常在本模块内收敛，chat_text/chat_json 失败返回 None，绝不向刮削/统计链路抛错；
- 成功响应写入 llm_cache（scope + 请求内容 hash），命中缓存不发起 HTTP 请求；
- 仅使用 requests（已在依赖中），PyInstaller 打包无新增负担。
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any

import requests

try:
    from backend.config import AppConfig
    from backend.services import db_service
except ImportError:
    from config import AppConfig
    from services import db_service

logger = logging.getLogger(__name__)

# 缓存作用域
SCOPE_SCRAPE_QUERY = "scrape_query"
SCOPE_VIEWING_REPORT = "viewing_report"
SCOPE_RECOMMEND_RERANK = "recommend_rerank"

# 连通性测试不做缓存，单独 scope
_CONNECT_TIMEOUT_FLOOR = 5


class LLMNotReadyError(Exception):
    """大模型未启用或未配置 Key。业务方一般先判断 is_ready()，不会收到此异常。"""


def _load_config() -> Any:
    config = AppConfig()
    config.load_config()
    return config


def is_ready() -> bool:
    """总开关开启且 Key 已配置时才允许调用。"""
    try:
        config = _load_config()
        return bool(getattr(config, "LLM_ENABLED", False)) and bool(
            str(getattr(config, "LLM_API_KEY", "")).strip()
        )
    except Exception:
        return False


def feature_enabled(attr: str) -> bool:
    """子功能开关（LLM_SCRAPE_ENABLED / LLM_REPORT_ENABLED），同时要求总开关就绪。"""
    if not is_ready():
        return False
    try:
        return bool(getattr(_load_config(), attr, False))
    except Exception:
        return False


def _endpoint(base_url: str) -> str:
    return f"{str(base_url).rstrip('/')}/chat/completions"


def _request_hash(model: str, system: str, user: str) -> str:
    payload = json.dumps(
        {"model": model, "system": system, "user": user}, ensure_ascii=False, sort_keys=True
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _strip_code_fence(text: str) -> str:
    """去掉模型常见的 ```json ... ``` 包裹。"""
    value = str(text or "").strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", value, re.DOTALL | re.IGNORECASE)
    return fence.group(1).strip() if fence else value


def _extract_json(text: str) -> Any:
    """从模型响应中提取 JSON：先整体解析，再截取首个 {...}/[...] 块。"""
    cleaned = _strip_code_fence(text)
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        pass
    for pattern in (r"\{.*\}", r"\[.*\]"):
        match = re.search(pattern, cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                continue
    return None


def _do_request(
    model: str,
    base_url: str,
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    temperature: float,
    timeout: int,
) -> dict[str, Any]:
    """发起一次原始 chat/completions 请求，返回解析后的 body dict 或抛异常。"""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    response = requests.post(
        _endpoint(base_url),
        json=payload,
        headers=headers,
        timeout=(max(_CONNECT_TIMEOUT_FLOOR, min(timeout, 10)), timeout),
    )
    response.raise_for_status()
    return response.json()


def chat_text(
    system_prompt: str,
    user_prompt: str,
    scope: str,
    request_meta: dict | None = None,
    *,
    use_cache: bool = True,
    max_tokens: int = 2048,
    temperature: float = 0.3,
    timeout: int | None = None,
) -> str | None:
    """发起一次对话补全，返回文本；未就绪或任何失败返回 None（业务方据此降级）。

    scope 用于缓存隔离；request_meta 仅记录非敏感排查信息（片名/窗口等）。
    timeout 可覆盖配置值（如 G2 精排要求 10s 内回退）。

    自动适配 reasoning 模型：当模型消耗大量 token 在思考链上导致
    finish_reason=length 且 content 为空时，会用 2 倍 max_tokens 重试一次。
    """
    if not is_ready():
        return None

    config = _load_config()
    model = str(getattr(config, "LLM_MODEL", "") or "").strip()
    base_url = str(getattr(config, "LLM_BASE_URL", "") or "").strip()
    api_key = str(getattr(config, "LLM_API_KEY", "") or "").strip()
    req_timeout = int(timeout) if timeout else int(getattr(config, "LLM_TIMEOUT", 15) or 15)
    key_hash = _request_hash(model, system_prompt, user_prompt)

    if use_cache:
        try:
            cached = db_service.get_llm_cache(scope, key_hash)
            if cached and cached.get("response_text"):
                logger.debug("LLM 缓存命中 scope=%s", scope)
                return cached["response_text"]
        except Exception as exc:
            logger.debug("LLM 缓存读取失败，继续请求: %s", exc)

    body = None
    actual_max = max_tokens
    for attempt in range(2):
        try:
            body = _do_request(
                model, base_url, api_key,
                system_prompt, user_prompt,
                actual_max, temperature, req_timeout,
            )
        except requests.RequestException as exc:
            logger.warning("LLM 请求失败（网络/超时），降级处理: %s", exc)
            return None

        try:
            msg = body["choices"][0]["message"]
            content = str(msg.get("content") or "").strip()
            finish_reason = body["choices"][0].get("finish_reason", "")
            # 如果有 content 就直接用，不用看 finish_reason
            if content:
                break
            # content 为空且被截断：reasoning 模型思考链耗尽预算，放大重试
            if finish_reason == "length" and attempt == 0:
                usage = body.get("usage", {})
                completion_tokens = usage.get("completion_tokens", 0)
                logger.info(
                    "LLM reasoning 模型耗尽 max_tokens=%d（completion=%d），放大到 %d 重试 scope=%s",
                    actual_max, completion_tokens, actual_max * 2, scope,
                )
                actual_max = min(actual_max * 2, 8192)
                continue
            # content 为空且不是截断，或已经重试过：放弃
            return None
        except (KeyError, IndexError, TypeError):
            logger.warning("LLM 响应结构异常，降级处理: %s", body)
            return None

    # 此时 body 一定有 content
    try:
        text = str(body["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError):
        return None
    if not text:
        return None

    if use_cache:
        try:
            db_service.set_llm_cache(
                scope, key_hash, text, model=model, request_meta=request_meta or {}
            )
        except Exception as exc:
            logger.debug("LLM 缓存写入失败（不影响本次结果）: %s", exc)
    return text


def chat_json(
    system_prompt: str,
    user_prompt: str,
    scope: str,
    request_meta: dict | None = None,
    *,
    use_cache: bool = True,
    max_tokens: int = 1024,
    temperature: float = 0.2,
    timeout: int | None = None,
) -> Any:
    """要求模型返回 JSON，解析为 dict/list；无法解析返回 None。

    缓存的是模型原始文本，命中后同样走 JSON 解析，保证返回类型一致。
    """
    text = chat_text(
        system_prompt,
        user_prompt,
        scope,
        request_meta,
        use_cache=use_cache,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
    )
    if text is None:
        return None
    parsed = _extract_json(text)
    if parsed is None:
        logger.warning("LLM 返回内容无法解析为 JSON（scope=%s）: %.200s", scope, text)
    return parsed


def test_connection() -> dict:
    """连通性测试：用一次极简调用验证 base_url / Key / 模型是否可用。

    自动适配 reasoning 模型：若思考链耗尽预算导致 content 为空，
    会用更大的 max_tokens 重试一次。
    返回 {"ok": bool, "message": str, "model": str}，不抛异常。
    """
    config = _load_config()
    if not str(getattr(config, "LLM_API_KEY", "")).strip():
        return {"ok": False, "message": "未配置 API Key", "model": ""}

    base_url = str(getattr(config, "LLM_BASE_URL", "")).strip()
    model = str(getattr(config, "LLM_MODEL", "")).strip()
    api_key = str(getattr(config, "LLM_API_KEY", "")).strip()
    if not base_url or not model:
        return {"ok": False, "message": "base_url 或模型名为空", "model": model}

    user_content = "请用一句话回复：连接成功，并附带上当前模型名称。"
    body = None
    actual_max = 512  # reasoning 模型至少需要这个量级
    try:
        for attempt in range(2):
            body = _do_request(model, base_url, api_key, "", user_content, actual_max, 0.0, 15)
            try:
                msg = body["choices"][0]["message"]
                content = str(msg.get("content") or "").strip()
                finish_reason = body["choices"][0].get("finish_reason", "")
                if content:
                    break
                if finish_reason == "length" and attempt == 0:
                    actual_max = min(actual_max * 2, 8192)
                    continue
                return {"ok": True, "message": f"连接成功，但模型回复为空（可能是纯思考链模型）", "model": model}
            except (KeyError, IndexError, TypeError):
                return {"ok": False, "message": "响应结构异常，可能不是 OpenAI 兼容端点", "model": model}
    except requests.RequestException as exc:
        status_code = getattr(exc.response, "status_code", None) if getattr(exc, "response", None) else None
        status_text = ""
        if status_code == 401:
            status_text = "API Key 无效或已失效（401）"
        elif status_code == 404:
            status_text = "端点或模型不存在（404），请检查 base_url 与模型名"
        elif status_code == 429:
            status_text = "触发限流或欠费（429），请检查账户额度"
        elif status_code:
            status_text = f"服务返回 {status_code}"
        else:
            status_text = f"网络连接失败：{exc}"
        return {"ok": False, "message": status_text, "model": model}

    try:
        final_content = str(body["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError):
        return {"ok": False, "message": "响应结构异常", "model": model}

    return {"ok": True, "message": f"连接成功，模型回复：{final_content or '(空)'}", "model": model}
