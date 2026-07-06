from __future__ import annotations

from pathlib import Path


TARGETS = sorted(Path("backend").rglob("*.py"))

MOJIBAKE_MARKERS = [
    "\u7487",
    "\u9352",
    "\u9429",
    "\u93b8",
    "\u7f02",
    "\u6f76",
    "\u93cd",
    "\u9427",
    "\u95c3",
    "\u5677",
    "\u6d5c",
    "\u935a",
    "\u9354",
    "\u6d93",
    "\u6d42",
    "\u7470",
    "\u6d93",
    "\ufffd",
]


def main() -> int:
    failures: list[str] = []
    for path in TARGETS:
        if not path.exists():
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if any(marker in line for marker in MOJIBAKE_MARKERS):
                failures.append(f"{path}:{line_no}: {line.strip()}")

    if failures:
        print("Potential mojibake found:")
        print("\n".join(failures))
        return 1

    print("No mojibake markers found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
