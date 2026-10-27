<template>
  <main class="stats-page">
    <section class="stats-hero">
      <div class="hero-copy">
        <span class="eyebrow">VIEWING INSIGHT</span>
        <h1>观影统计</h1>
        <p>把片库快照和近期真实播放行为分开看，数据更清楚，也更可信。</p>
      </div>

      <div class="hero-actions">
        <div class="range-switch" role="group" aria-label="统计时间范围">
          <button
            v-for="range in ranges"
            :key="range.value"
            type="button"
            :class="{ active: rangeDays === range.value }"
            :aria-pressed="rangeDays === range.value"
            @click="selectRange(range.value)"
          >
            {{ range.label }}
          </button>
        </div>
        <button class="refresh-button" :disabled="loading" type="button" @click="loadStats">
          <span class="refresh-mark" :class="{ spinning: loading }">↻</span>
          {{ loading ? '同步中' : '刷新数据' }}
        </button>
      </div>
    </section>

    <section v-if="loading && !hasSnapshot" class="state-card" aria-live="polite">
      正在整理真实的观影记录…
    </section>

    <section v-else-if="!hasSnapshot" class="state-card error-card" aria-live="polite">
      <strong>暂时无法加载观影统计</strong>
      <p>{{ error || '请确认媒体服务已经启动后再试。' }}</p>
      <button type="button" class="retry-button" @click="loadStats">重新加载</button>
    </section>

    <template v-else>
      <section v-if="error && !hasStats && poolCount > 0" class="notice-card" role="status">
        <span>{{ error }}，仅展示片库快照。</span>
        <button type="button" @click="loadStats">重试</button>
      </section>

      <section v-if="error && hasStats" class="notice-card" role="status">
        <span>最新数据同步失败，当前显示上次成功加载的结果。</span>
        <button type="button" @click="loadStats">重试</button>
      </section>

      <section class="snapshot-strip" aria-label="片库快照">
        <div>
          <span>片库快照</span>
          <strong>{{ hasStats ? formatNumber(overview.logicalTitles ?? overview.total) : '--' }}</strong>
          <small>部逻辑作品</small>
        </div>
        <div>
          <span>资源条目</span>
          <strong>{{ hasStats ? formatNumber(overview.resourceEntries ?? overview.total) : '--' }}</strong>
          <small>个可播放版本</small>
        </div>
        <div>
          <span>已产生进度</span>
          <strong>{{ formatNumber(hasStats ? overview.watched : 0) }}</strong>
          <small>个资源条目</small>
        </div>
        <div>
          <span>收藏资源</span>
          <strong>{{ formatNumber(hasStats ? overview.favorite : 0) }}</strong>
          <small>个资源条目</small>
        </div>
        <div class="pool-stat">
          <span>虚拟片库</span>
          <strong>{{ formatNumber(poolCount) }}</strong>
          <small>条精选数据</small>
        </div>
        <p class="snapshot-note">片库快照不受当前时间范围影响；同一影片的多个版本会分别计入资源条目。</p>
      </section>

      <template v-if="hasStats">
        <section class="section-heading">
          <div>
            <span class="eyebrow">REAL ACTIVITY</span>
            <h2>近 {{ displayDays }} 天观影行为</h2>
            <p>{{ activitySourceLabel }} · 仅统计本地记录到的播放活动</p>
          </div>
          <span v-if="lastUpdated" class="updated-at">更新于 {{ formatUpdatedAt(lastUpdated) }}</span>
        </section>

        <section class="metric-grid" aria-label="近期开播数据">
          <article class="metric-card accent-violet">
            <span>观看时长</span>
            <strong>{{ formatDecimal(activity.watchHours) }}</strong>
            <small>小时</small>
            <p>活跃日均 {{ formatDecimal(activity.averageDailyMinutes) }} 分钟</p>
          </article>
          <article class="metric-card accent-teal">
            <span>活跃天数</span>
            <strong>{{ formatNumber(activity.activeDays) }}</strong>
            <small>天</small>
            <p>覆盖 {{ displayDays }} 天统计周期</p>
          </article>
          <article class="metric-card accent-coral">
            <span>播放次数</span>
            <strong>{{ formatNumber(activity.playCount) }}</strong>
            <small>次</small>
            <p>涉及 {{ formatNumber(activity.uniqueTitles) }} 部作品</p>
          </article>
          <article class="metric-card accent-gold">
            <span>当前连续观看</span>
            <strong>{{ formatNumber(activity.currentStreak) }}</strong>
            <small>天</small>
            <p>最长连续 {{ formatNumber(activity.longestStreak) }} 天</p>
          </article>
        </section>

        <section class="insight-grid">
          <article class="panel personality-panel">
            <div class="panel-heading">
              <div>
                <span class="eyebrow">VIEWING PROFILE</span>
                <h2>观影人格</h2>
              </div>
              <span class="confidence">{{ isInsufficient ? '样本不足' : `${formatDecimal(personality.confidence)}% 置信度` }}</span>
            </div>

            <template v-if="isInsufficient">
              <div class="profile-empty">
                <strong>还在认识你的观影习惯</strong>
                <p>继续积累有效播放记录后，这里会生成基于真实行为的观影人格。</p>
                <div class="requirement-list">
                  <span>至少 2 个有进度的片集或影片</span>
                  <span>至少 1 个活跃观看日</span>
                  <span>累计 30 分钟观看时长</span>
                </div>
              </div>
            </template>
            <template v-else>
              <div class="profile-title-row">
                <span class="profile-code">{{ personality.code }}</span>
                <div>
                  <h3>{{ personality.title || personality.name }}</h3>
                  <p>{{ personality.summary }}</p>
                </div>
              </div>
              <p class="profile-description">{{ personality.description }}</p>
              <div v-if="profileTags.length" class="trait-list">
                <span v-for="trait in profileTags" :key="trait">{{ trait }}</span>
              </div>
              <div class="dimension-list">
                <div v-for="dimension in profileDimensions" :key="dimension.label" class="dimension-row">
                  <span>{{ dimension.label }}</span>
                  <div class="dimension-track"><i :style="{ width: `${dimension.value}%` }" /></div>
                  <strong>{{ Math.round(dimension.value) }}</strong>
                </div>
              </div>
            </template>
          </article>

          <article class="panel rhythm-panel">
            <div class="panel-heading">
              <div>
                <span class="eyebrow">VIEWING RHYTHM</span>
                <h2>本周期节奏</h2>
              </div>
            </div>
            <div class="rhythm-main">
              <strong>{{ peakHourLabel }}</strong>
              <span>最常开始播放的时段</span>
            </div>
            <dl class="rhythm-list">
              <div>
                <dt>单次平均</dt>
                <dd>{{ formatDecimal(activity.averageSessionMinutes) }} 分钟</dd>
              </div>
              <div>
                <dt>活跃日均</dt>
                <dd>{{ formatDecimal(activity.averageDailyMinutes) }} 分钟</dd>
              </div>
              <div>
                <dt>活跃作品</dt>
                <dd>{{ formatNumber(activity.uniqueTitles) }} 部</dd>
              </div>
            </dl>
            <p class="panel-footnote">播放次数按开始播放记录计算；观看时长优先采用播放器心跳记录。</p>
          </article>
        </section>

        <section class="llm-report-section">
          <article class="panel llm-report-panel">
            <div class="panel-heading">
              <div>
                <span class="eyebrow">AI REPORT</span>
                <h2>AI 观影报告</h2>
              </div>
              <span
                v-if="llmReport && llmReport.source !== 'empty'"
                class="report-source"
                :class="`source-${llmReport.source}`"
              >{{ sourceLabel }}</span>
            </div>

            <div v-if="!llmReport && !llmReportLoading" class="report-intro">
              <p>基于近期真实观影数据生成自然语言阶段总结：看了什么、风格有何变化、可以试试什么。</p>
              <button type="button" class="report-generate-btn" @click="loadLlmReport(false)">
                生成观影报告
              </button>
              <p class="panel-footnote">
                未配置大模型时使用内置模板生成；如需 AI 版本，可在「设置 → AI 大模型增强」中配置。
              </p>
            </div>

            <div v-else-if="llmReportLoading" class="report-loading">
              正在分析近 {{ reportDays }} 天的观影数据…
            </div>

            <template v-else-if="llmReport">
              <div class="report-toolbar">
                <div class="report-days-switch">
                  <button
                    v-for="d in [7, 30, 90]"
                    :key="d"
                    type="button"
                    :class="{ active: reportDays === d }"
                    @click="selectReportDays(d)"
                  >近 {{ d }} 天</button>
                </div>
                <div class="report-toolbar-right">
                  <button
                    v-if="llmReport.source === 'llm' && llmReport.templateReport"
                    type="button"
                    class="report-compare-btn"
                    :class="{ active: showCompare }"
                    @click="toggleCompare"
                  >{{ showCompare ? '关闭对比' : '对比模板版' }}</button>
                  <button
                    v-if="llmReport.source !== 'empty'"
                    type="button"
                    class="report-regenerate-btn"
                    :disabled="llmReportLoading"
                    @click="loadLlmReport(true)"
                  >重新生成</button>
                </div>
              </div>

              <p v-if="llmReport.message" class="report-message">{{ llmReport.message }}</p>
              <p v-if="llmReportStale" class="report-message report-stale">
                报告生成后观影数据已有更新，点击「重新生成」可获取最新解读。
              </p>

              <div v-if="llmReport.source === 'empty'" class="report-empty">
                近 {{ reportDays }} 天暂无有效观影记录，先去看几部影片吧。
              </div>
              <div v-else-if="showCompare && llmReport.templateReport" class="report-compare">
                <div class="compare-col">
                  <div class="compare-label source-llm">AI 生成</div>
                  <article class="report-markdown" v-html="llmReportHtml"></article>
                </div>
                <div class="compare-col">
                  <div class="compare-label source-template">模板生成</div>
                  <article class="report-markdown" v-html="templateReportHtml"></article>
                </div>
              </div>
              <article v-else class="report-markdown" v-html="llmReportHtml"></article>

              <p v-if="llmReport.generatedAt" class="panel-footnote report-footnote">
                <template v-if="llmReport.source === 'llm' && llmReport.model">
                  由 {{ llmReport.model }} 生成 ·
                </template>
                {{ formatReportTime(llmReport.generatedAt) }}
              </p>
            </template>
          </article>
        </section>

        <section class="section-heading compact-heading">
          <div>
            <span class="eyebrow">ACTIVITY PATTERN</span>
            <h2>观看节奏</h2>
          </div>
        </section>

        <section class="activity-layout">
          <article class="panel trend-panel">
            <div class="panel-heading">
              <div>
                <h3>{{ trendGranularityLabel }}观看时长</h3>
                <p>{{ selectedTrend.label || '尚无播放记录' }} · {{ formatDecimal(selectedTrend.minutes) }} 分钟 · {{ formatNumber(selectedTrend.playCount) }} 次播放</p>
              </div>
              <span class="panel-value"><small>峰值</small>{{ formatDecimal(trendPeakMinutes) }}<em>分钟</em></span>
            </div>
            <div
              v-if="hasActivity"
              class="trend-chart"
              role="group"
              tabindex="0"
              :aria-label="`${trendGranularityLabel}观看时长趋势图`"
              @mouseleave="clearTrendSelection"
              @blur="clearTrendSelection"
              @keydown.left.prevent="moveTrendSelection(-1)"
              @keydown.right.prevent="moveTrendSelection(1)"
            >
              <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true" focusable="false">
                <defs>
                  <linearGradient id="trend-bar-fill" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stop-color="#c2b7ff" stop-opacity="1" />
                    <stop offset="100%" stop-color="#7260e7" stop-opacity="0.76" />
                  </linearGradient>
                </defs>
                <g class="trend-grid">
                  <line v-for="line in trendGridLines" :key="line" x1="0" x2="100" :y1="line" :y2="line" />
                </g>
                <rect
                  v-if="selectedTrend.index >= 0"
                  class="trend-selection"
                  :x="selectedTrend.x"
                  y="10"
                  :width="selectedTrend.width"
                  height="82"
                  rx="1.1"
                />
                <rect
                  v-for="point in trendBins"
                  v-show="point.visible"
                  :key="`bar-${point.key}`"
                  class="trend-bar"
                  :class="{ selected: selectedTrend.key === point.key, 'play-only': point.playOnly }"
                  :x="point.x"
                  :y="point.y"
                  :width="point.width"
                  :height="point.height"
                  rx="0.8"
                />
                <rect
                  v-for="point in trendBins"
                  :key="`hit-${point.key}`"
                  class="trend-hit-area"
                  :x="point.x"
                  y="8"
                  :width="point.width"
                  height="85"
                  rx="0.8"
                  aria-hidden="true"
                  :title="`${point.label} · ${formatDecimal(point.minutes)} 分钟 · ${formatNumber(point.playCount)} 次播放`"
                  @mouseenter="selectTrendPoint(point.index)"
                  @click="selectTrendPoint(point.index)"
                />
              </svg>
              <div class="trend-axis" aria-hidden="true">
                <span v-for="tick in trendAxisTicks" :key="tick.key" :style="{ left: `${tick.center}%` }">{{ tick.shortLabel }}</span>
              </div>
              <div class="trend-context">
                <span>{{ trendGranularityLabel }}聚合</span>
                <span>{{ activeTrendBinCount }} 个活跃{{ trendGranularityLabel === '每日' ? '日' : '周期' }}</span>
              </div>
              <span class="sr-only" aria-live="polite">{{ selectedTrend.label }}，{{ formatDecimal(selectedTrend.minutes) }} 分钟，{{ formatNumber(selectedTrend.playCount) }} 次播放</span>
            </div>
            <div v-else class="chart-empty">此周期内还没有可用的播放活动。</div>
          </article>

          <article class="panel heatmap-panel">
            <div class="panel-heading">
              <div>
                <h3>开始播放时段</h3>
                <p>按播放开始时间分布</p>
              </div>
            </div>
            <div v-if="hasActivity" class="hour-grid">
              <button
                v-for="hour in activity.hourDistribution"
                :key="hour.hour"
                type="button"
                class="hour-cell"
                :style="hourCellStyle(hour)"
                :title="`${hour.label} · ${formatNumber(hour.value)} 次开始播放`"
              >
                <span>{{ hour.label }}</span>
                <b>{{ hour.value || '' }}</b>
              </button>
            </div>
            <div v-else class="chart-empty">暂无时段分布。</div>
          </article>

          <article class="panel weekday-panel">
            <div class="panel-heading">
              <div>
                <h3>一周活跃度</h3>
                <p>按开始播放次数统计</p>
              </div>
            </div>
            <div v-if="hasActivity" class="weekday-list">
              <div v-for="day in activity.weekdayDistribution" :key="day.weekday" class="weekday-row">
                <span>{{ day.label }}</span>
                <div><i :style="weekdayBarStyle(day)" /></div>
                <b>{{ day.value }}</b>
              </div>
            </div>
            <div v-else class="chart-empty">暂无周内分布。</div>
          </article>
        </section>

        <section class="section-heading compact-heading">
          <div>
            <span class="eyebrow">LIBRARY SNAPSHOT</span>
            <h2>片库构成</h2>
            <p>以下数据反映当前片库和已保存的播放进度，不受时间范围影响。</p>
          </div>
        </section>

        <section class="library-layout">
          <article class="panel category-panel">
            <div class="panel-heading">
              <div><h3>内容分类</h3><p>支持的分类可点击前往片库浏览</p></div>
            </div>
            <div v-if="categoryDistribution.length" class="distribution-list">
              <button
                v-for="item in categoryDistribution"
                :key="item.label"
                type="button"
                class="distribution-row"
                :class="{ disabled: !isBrowsableCategory(item.label) }"
                :disabled="!isBrowsableCategory(item.label)"
                @click="openCategory(item.label)"
              >
                <span>{{ item.label }}</span>
                <div><i :style="{ width: `${clampPercent(item.percent)}%` }" /></div>
                <strong>{{ item.value }}</strong>
              </button>
            </div>
            <div v-else class="chart-empty">片库尚无可分类内容。</div>
          </article>

          <article class="panel completion-panel">
            <div class="panel-heading">
              <div><h3>观看进度</h3><p>完成阈值为播放进度 90%</p></div>
            </div>
            <div class="completion-content">
              <div class="completion-ring" :style="completionRingStyle">
                <div><strong>{{ formatDecimal(overview.completionRate) }}%</strong><span>完成率</span></div>
              </div>
              <dl>
                <div v-for="item in completionStats" :key="item.label">
                  <dt>{{ item.label }}</dt>
                  <dd>{{ item.value }}</dd>
                </div>
              </dl>
            </div>
          </article>

          <article class="panel source-panel">
            <div class="panel-heading"><div><h3>来源分布</h3><p>按资源条目统计</p></div></div>
            <div v-if="sourceDistribution.length" class="source-list">
              <div v-for="item in sourceDistribution" :key="item.label">
                <span>{{ item.label }}</span><b>{{ item.value }}</b>
              </div>
            </div>
            <div v-else class="chart-empty">暂无来源数据。</div>
            <div v-if="tagDistribution.length" class="tag-summary">
              <span class="tag-summary-title">片库常见标签</span>
              <span v-for="item in tagDistribution" :key="item.label" class="tag-chip">{{ item.label }} <b>{{ item.value }}</b></span>
            </div>
          </article>
        </section>

        <section class="bottom-layout">
          <article class="panel titles-panel">
            <div class="panel-heading">
              <div>
                <span class="eyebrow">MOST WATCHED</span>
                <h2>本周期常看内容</h2>
              </div>
            </div>
            <div v-if="activity.topTitles?.length" class="title-list">
              <button
                v-for="(item, index) in activity.topTitles"
                :key="item.id"
                type="button"
                class="title-row"
                :class="{ disabled: item.available === false }"
                :disabled="item.available === false"
                @click="openDetail(item.id)"
              >
                <span class="title-rank">0{{ index + 1 }}</span>
                <img v-if="item.coverUrl" :src="item.coverUrl" :alt="item.title" />
                <span v-else class="title-cover-placeholder">{{ initialOf(item.title) }}</span>
                <span class="title-copy">
                  <strong>{{ item.title || '未命名作品' }}</strong>
                  <small>{{ item.available === false ? '已从片库移除 · ' : '' }}{{ item.category || '影视' }} · {{ formatDecimal(item.watchMinutes) }} 分钟 · {{ item.playCount }} 次播放</small>
                </span>
                <span class="row-arrow">›</span>
              </button>
            </div>
            <div v-else class="chart-empty">此周期内还没有足够的播放记录。</div>
          </article>

          <article class="panel history-panel">
            <div class="panel-heading">
              <div>
                <span class="eyebrow">CONTINUE WATCHING</span>
                <h2>最近播放</h2>
              </div>
            </div>
            <div v-if="recentHistory.length" class="history-list">
              <article v-for="item in recentHistory" :key="item.id" class="history-row">
                <img v-if="historyCover(item)" :src="historyCover(item)" :alt="item.title" />
                <span v-else class="history-cover-placeholder">{{ initialOf(item.title) }}</span>
                <div class="history-copy">
                  <strong>{{ item.title || '未命名作品' }}</strong>
                  <span>{{ formatDate(item.lastPlayTime) }} · 已看 {{ formatDecimal(item.progressPercent) }}%</span>
                  <i><b :style="{ width: `${clampPercent(item.progressPercent)}%` }" /></i>
                </div>
                <div class="history-actions">
                  <button type="button" title="查看详情" @click="openDetail(item.id)">详情</button>
                  <button type="button" class="play-action" title="继续播放" @click="resumeMovie(item)">播放</button>
                </div>
              </article>
            </div>
            <div v-else class="chart-empty">播放一部作品后，最近播放会显示在这里。</div>
          </article>
        </section>
      </template>

      <!-- 虚拟片库外部热度看板：独立于观影统计（见任务 C） -->
      <section class="hotness-section" aria-label="虚拟片库外部热度">
        <div class="section-heading hotness-heading">
          <div>
            <span class="eyebrow">EXTERNAL HEAT</span>
            <h2>虚拟片库热度</h2>
            <p>TMDB 精选条目的外部热度快照（popularity / 投票数），与本地播放行为无关</p>
          </div>
          <button
            class="refresh-button"
            :disabled="hotnessLoading"
            type="button"
            @click="loadHotness"
          >
            <span class="refresh-mark" :class="{ spinning: hotnessLoading }">↻</span>
            {{ hotnessLoading ? '同步中' : '刷新热度' }}
          </button>
        </div>

        <section
          v-if="!hotnessLoading && !topHotnessCount && !hotnessError"
          class="state-card"
        >
          暂无热度快照。在设置页触发热度刷新，或等待每日 05:00 自动采集后查看趋势。
        </section>
        <section v-else-if="hotnessError && !topHotnessCount" class="state-card error-card">
          <strong>热度榜加载失败</strong>
          <p>{{ hotnessError }}</p>
        </section>

        <div v-else class="hotness-layout">
          <article class="panel hotness-top-panel">
            <div class="panel-heading">
              <div>
                <h3>热度 Top {{ topHotnessCount }}</h3>
                <p>按最近一次快照 popularity 排序 · 点击行查看趋势</p>
              </div>
            </div>
            <div v-if="topHotnessCount" class="hotness-top-list">
              <button
                v-for="(item, index) in hotnessItems"
                :key="item.poolId"
                type="button"
                class="hotness-row"
                :class="{ active: item.poolId === selectedPoolId }"
                @click="selectHotnessItem(item)"
              >
                <span class="hotness-rank">{{ index + 1 }}</span>
                <img v-if="posterUrl(item.posterPath)" :src="posterUrl(item.posterPath)" :alt="item.title" loading="lazy" />
                <span v-else class="hotness-cover-placeholder">{{ initialOf(item.title) }}</span>
                <span class="hotness-copy">
                  <strong>{{ item.title || '未命名作品' }}</strong>
                  <small>{{ mediaTypeLabel(item.mediaType) }}{{ item.year ? ` · ${item.year}` : '' }} · {{ formatNumber(item.voteCount) }} 票</small>
                  <i class="hotness-bar"><b :style="{ width: hotnessBarWidth(item.popularity) }" /></i>
                </span>
                <span class="hotness-pop">{{ formatPop(item.popularity) }}</span>
              </button>
            </div>
            <div v-else class="chart-empty">暂无热度快照数据。</div>
          </article>

          <article class="panel hotness-trend-panel">
            <div class="panel-heading">
              <div>
                <h3>{{ selectedHotness?.title || '热度趋势' }}</h3>
                <p>{{ trendSummary }}</p>
              </div>
              <span class="panel-value"><small>最新 popularity</small>{{ formatPop(currentPop) }}</span>
            </div>
            <div v-if="poolTrendLoading" class="chart-empty">正在加载趋势…</div>
            <div v-else-if="trendPoints.length >= 2" class="heat-trend-chart">
              <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true" focusable="false">
                <defs>
                  <linearGradient id="heat-area-fill" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stop-color="#f6b45c" stop-opacity="0.32" />
                    <stop offset="100%" stop-color="#f6b45c" stop-opacity="0.02" />
                  </linearGradient>
                </defs>
                <polygon :points="trendAreaPoints" fill="url(#heat-area-fill)" />
                <polyline
                  :points="trendLinePoints"
                  fill="none"
                  stroke="#f6b45c"
                  stroke-width="1.8"
                  stroke-linejoin="round"
                  stroke-linecap="round"
                  vector-effect="non-scaling-stroke"
                />
                <rect
                  v-for="p in trendPoints"
                  :key="p.key"
                  :x="p.x - 1.5"
                  :y="p.y - 1.5"
                  width="3"
                  height="3"
                  rx="0.8"
                  fill="#fff8ef"
                  stroke="#f6b45c"
                  stroke-width="0.5"
                />
              </svg>
              <div class="trend-axis" aria-hidden="true">
                <span v-for="t in trendTicks" :key="t.key" :style="{ left: `${t.center}%` }">{{ t.label }}</span>
              </div>
              <div class="trend-context">
                <span>popularity 走势</span>
                <span>{{ poolTrend.length }} 次快照</span>
              </div>
            </div>
            <div v-else class="chart-empty">
              {{ poolTrend.length === 1 ? '仅采集到 1 次快照，需多次采集后才会形成趋势曲线。' : '该条目还没有热度快照，稍后在每日自动采集后回来查看。' }}
            </div>
          </article>
        </div>
      </section>
    </template>
  </main>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getStats } from '@/api/movie'
import { startPlay } from '@/composables/usePlayer'
import { get } from '@/api/request'
import { getTopHotness, getPoolHotness } from '@/api/hotness'
import { generateViewingReport, getLastViewingReport } from '@/api/llm'

const router = useRouter()
const ranges = [
  { label: '7 天', value: 7 },
  { label: '30 天', value: 30 },
  { label: '90 天', value: 90 },
  { label: '365 天', value: 365 }
]

const emptyOverview = Object.freeze({
  total: 0,
  resourceEntries: 0,
  logicalTitles: 0,
  watched: 0,
  completed: 0,
  inProgress: 0,
  favorite: 0,
  completionRate: 0
})
const emptyActivity = Object.freeze({
  watchHours: 0,
  activeDays: 0,
  playCount: 0,
  uniqueTitles: 0,
  averageDailyMinutes: 0,
  averageSessionMinutes: 0,
  currentStreak: 0,
  longestStreak: 0,
  peakHour: null,
  dataSource: 'none',
  dailyTrend: [],
  hourDistribution: [],
  weekdayDistribution: [],
  topTitles: []
})

const stats = ref(null)
const loading = ref(false)
const error = ref('')
const rangeDays = ref(90)
const lastUpdated = ref(null)
const selectedTrendIndex = ref(-1)
const poolCount = ref(0)

// —— 虚拟片库外部热度看板（独立数据源，见任务 C）——
const TMDB_POSTER = 'https://image.tmdb.org/t/p/w342'
const TOP_HOTNESS_LIMIT = 10
const hotnessItems = ref([])
const hotnessLoading = ref(false)
const hotnessError = ref('')
const selectedPoolId = ref('')
const poolTrend = ref([])
const poolTrendLoading = ref(false)
const trendRequestId = ref(0) // 竞态防护：只采纳最后一次请求的结果

const selectedHotness = computed(
  () => hotnessItems.value.find(item => item.poolId === selectedPoolId.value) || hotnessItems.value[0] || null
)
const hotnessMaxPop = computed(() => Math.max(1, ...hotnessItems.value.map(item => Number(item.popularity || 0))))
const topHotnessCount = computed(() => hotnessItems.value.length)

function posterUrl(path) {
  return path ? `${TMDB_POSTER}${path}` : ''
}

function mediaTypeLabel(type) {
  if (type === 'tv') return '剧集'
  if (type === 'movie') return '电影'
  return '影视'
}

function formatPop(value) {
  const number = Number(value || 0)
  return number > 0 ? number.toLocaleString('zh-CN', { maximumFractionDigits: number < 10 ? 1 : 0 }) : '—'
}

function hotnessBarWidth(value) {
  const number = Number(value || 0)
  return `${Math.max(0, Math.min(100, number / hotnessMaxPop.value * 100)).toFixed(1)}%`
}

function formatFetchedLabel(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit' }).format(date)
}

// 趋势折线：popularity 归一化到 100x100 坐标（留边距）
const trendPoints = computed(() => {
  const items = asArray(poolTrend.value)
  if (!items.length) return []
  const values = items.map(item => Number(item.popularity || 0))
  const max = Math.max(...values)
  const min = Math.min(...values)
  const span = Math.max(1e-9, max - min)
  const count = items.length
  return items.map((item, index) => {
    const x = count === 1 ? 50 : 5 + index / (count - 1) * 90
    const y = 7 + (1 - (Number(item.popularity || 0) - min) / span) * 86
    return {
      key: item.fetchedAt || String(index),
      x: Number(x.toFixed(3)),
      y: Number(y.toFixed(3)),
      label: formatFetchedLabel(item.fetchedAt),
      popularity: Number(item.popularity || 0)
    }
  })
})
const trendLinePoints = computed(() => trendPoints.value.map(p => `${p.x},${p.y}`).join(' '))
const trendAreaPoints = computed(() => {
  const points = trendPoints.value
  if (!points.length) return ''
  return `${points[0].x},93 ${points.map(p => `${p.x},${p.y}`).join(' ')} ${points.at(-1).x},93`
})
const trendTicks = computed(() => {
  const points = trendPoints.value
  if (!points.length) return []
  const desired = 4
  const indexes = points.length <= desired
    ? points.map((_, index) => index)
    : Array.from({ length: desired }, (_, index) => Math.round(index * (points.length - 1) / (desired - 1)))
  return [...new Set(indexes)].map(index => ({
    key: points[index].key,
    center: Number(points[index].x.toFixed(2)),
    label: points[index].label
  }))
})
const currentPop = computed(() => {
  const latest = asArray(poolTrend.value).at(-1)
  return latest ? Number(latest.popularity || 0) : 0
})
const trendSummary = computed(() => {
  const items = asArray(poolTrend.value)
  if (!items.length) return '暂无热度快照'
  if (items.length === 1) return `已有 1 次快照（${formatFetchedLabel(items[0].fetchedAt)}），需多次采集形成趋势`
  const first = Number(items[0].popularity || 0)
  const last = Number(items.at(-1).popularity || 0)
  const direction = last > first ? '上升' : last < first ? '下降' : '持平'
  return `${items.length} 次快照 · popularity ${direction} ${formatPop(Math.abs(last - first))}`
})

const hasStats = computed(() => stats.value !== null)
const hasSnapshot = computed(() => hasStats.value || poolCount.value > 0)
const overview = computed(() => stats.value?.overview || emptyOverview)
const activity = computed(() => stats.value?.activity || emptyActivity)
const displayDays = computed(() => Number(stats.value?.periodDays || activity.value.days || rangeDays.value))
const personality = computed(() => stats.value?.viewingPersonality || stats.value?.personality || {})
const isInsufficient = computed(() => !personality.value.code || personality.value.dataStatus === 'insufficient' || personality.value.code === 'XXX')
const profileTags = computed(() => {
  const tags = personality.value.tags ?? personality.value.traits ?? []
  return Array.isArray(tags) ? tags.filter(Boolean).slice(0, 5) : []
})
const profileDimensions = computed(() => [
  { label: '沉浸度', value: clampPercent(personality.value.scores?.focus) },
  { label: '偏好深度', value: clampPercent(personality.value.scores?.depth) },
  { label: '观看规律', value: clampPercent(personality.value.scores?.routine) }
])

// AI 观影报告（方向 G 落点③；未启用 AI 时后端返回模板报告）
const reportDays = ref(30)
const llmReport = ref(null)
const llmReportLoading = ref(false)
const llmReportStale = ref(false)
const showCompare = ref(false)

const sourceLabel = computed(() => {
  if (llmReport.value?.source === 'llm') return 'AI 生成'
  if (llmReport.value?.source === 'template') return '模板生成'
  return ''
})

/**
 * 极简 Markdown 渲染：先整体 HTML 转义（防注入），再做受限语法替换。
 * 仅支持标题、无序/有序列表、加粗、行内代码、段落；不引入第三方 markdown 依赖。
 */
function escapeHtml(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function renderInlineMarkdown(text) {
  return text
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
}

function renderMarkdown(markdown) {
  if (!markdown) return ''
  const lines = escapeHtml(markdown).replace(/\r\n/g, '\n').split('\n')
  const html = []
  let listType = null
  const closeList = () => {
    if (listType) {
      html.push(`</${listType}>`)
      listType = null
    }
  }
  for (const rawLine of lines) {
    const line = rawLine.trim()
    if (!line) {
      closeList()
      continue
    }
    let match
    if ((match = line.match(/^(#{1,4})\s+(.*)$/))) {
      closeList()
      const level = Math.min(match[1].length + 2, 6)
      html.push(`<h${level}>${renderInlineMarkdown(match[2])}</h${level}>`)
    } else if ((match = line.match(/^[-*]\s+(.*)$/))) {
      if (listType !== 'ul') {
        closeList()
        html.push('<ul>')
        listType = 'ul'
      }
      html.push(`<li>${renderInlineMarkdown(match[1])}</li>`)
    } else if ((match = line.match(/^\d+[.、)]\s+(.*)$/))) {
      if (listType !== 'ol') {
        closeList()
        html.push('<ol>')
        listType = 'ol'
      }
      html.push(`<li>${renderInlineMarkdown(match[1])}</li>`)
    } else {
      closeList()
      html.push(`<p>${renderInlineMarkdown(line)}</p>`)
    }
  }
  closeList()
  return html.join('')
}

const llmReportHtml = computed(() => renderMarkdown(llmReport.value?.report || ''))
const templateReportHtml = computed(() => renderMarkdown(llmReport.value?.templateReport || ''))

function formatReportTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('zh-CN', { hour12: false })
}

function toggleCompare() {
  showCompare.value = !showCompare.value
}

// 恢复上次生成的报告（后端持久化，零 LLM 成本）；找不到返回 false
async function restoreLastReport() {
  try {
    const res = await getLastViewingReport(reportDays.value)
    if (res?.found && res?.report?.report) {
      llmReport.value = res.report
      llmReportStale.value = !!res.stale
      if (llmReport.value.source !== 'llm') showCompare.value = false
      return true
    }
  } catch {
    // 恢复失败静默处理，让用户手动生成
  }
  return false
}

async function loadLlmReport(forceRefresh = false) {
  llmReportLoading.value = true
  try {
    // AI 报告请求时附带模板版，供「对比模板版」功能使用
    llmReport.value = await generateViewingReport(reportDays.value, forceRefresh, true)
    llmReportStale.value = false
    if (llmReport.value?.source !== 'llm') {
      showCompare.value = false
    }
  } catch (error) {
    // 后端失败通常会自身回退；到这里说明请求异常，保留旧报告并提示
    llmReport.value = {
      source: llmReport.value?.source === 'llm' ? 'template' : (llmReport.value?.source || 'template'),
      report: llmReport.value?.report || '',
      days: reportDays.value,
      message: `报告生成失败：${error.message}`
    }
  } finally {
    llmReportLoading.value = false
  }
}

function selectReportDays(days) {
  if (reportDays.value === days || llmReportLoading.value) return
  reportDays.value = days
  // 优先恢复该窗口的持久化报告，从未生成过才触发真实生成
  restoreLastReport().then((restored) => {
    if (!restored) loadLlmReport(false)
  })
}
const categoryDistribution = computed(() => asArray(stats.value?.categoryDistribution))
const sourceDistribution = computed(() => asArray(stats.value?.sourceDistribution).slice(0, 6))
const tagDistribution = computed(() => asArray(stats.value?.tagDistribution).slice(0, 8))
const completionStats = computed(() => asArray(stats.value?.completionStats))
const recentHistory = computed(() => asArray(stats.value?.recentHistory).slice(0, 6))
const hasActivity = computed(() => Number(activity.value.playCount || 0) > 0 || Number(activity.value.watchSeconds || 0) > 0)
const activitySourceLabel = computed(() => {
  if (activity.value.dataSource === 'events') return '来自播放行为记录'
  if (activity.value.dataSource === 'playback') return '来自已保存的播放进度'
  return '尚无播放行为记录'
})
const peakHourLabel = computed(() => {
  const hour = Number(activity.value.peakHour)
  return Number.isInteger(hour) && hour >= 0 && hour <= 23 ? `${String(hour).padStart(2, '0')}:00` : '暂无规律'
})

const trendGranularity = computed(() => {
  if (displayDays.value <= 30) return 'day'
  if (displayDays.value <= 120) return 'week'
  return 'month'
})
const trendBinSize = computed(() => trendGranularity.value === 'day' ? 1 : 7)
const trendGranularityLabel = computed(() => {
  if (trendGranularity.value === 'day') return '每日'
  if (trendGranularity.value === 'week') return '每周'
  return '每月'
})
const trendBins = computed(() => {
  const trend = asArray(activity.value.dailyTrend)
  if (!trend.length) return []

  const groups = []
  if (trendGranularity.value === 'month') {
    let monthKey = ''
    for (const item of trend) {
      const nextMonthKey = String(item.date || '').slice(0, 7)
      if (!groups.length || nextMonthKey !== monthKey) {
        groups.push([])
        monthKey = nextMonthKey
      }
      groups.at(-1).push(item)
    }
  } else {
    for (let start = 0; start < trend.length; start += trendBinSize.value) {
      groups.push(trend.slice(start, start + trendBinSize.value))
    }
  }

  const grouped = groups.map(items => {
    const first = items[0]
    const last = items.at(-1)
    const minutes = items.reduce((total, item) => total + Math.max(0, Number(item.minutes ?? item.value ?? 0)), 0)
    const playCount = items.reduce((total, item) => total + Math.max(0, Number(item.playCount || 0)), 0)
    const month = String(first.date || '').slice(5, 7).replace(/^0/, '')
    return {
      key: `${first.date}-${last.date}`,
      date: first.date,
      startLabel: first.label,
      endLabel: last.label,
      label: trendGranularity.value === 'month' ? `${month || first.label}月` : (items.length === 1 ? first.label : `${first.label}–${last.label}`),
      minutes: Number(minutes.toFixed(1)),
      playCount
    }
  })

  const maxMinutes = Math.max(1, ...grouped.map(item => item.minutes))
  const slotWidth = 100 / grouped.length
  const gap = Math.min(1.45, Math.max(0.44, slotWidth * 0.18))
  const width = Math.max(0.72, slotWidth - gap)
  return grouped.map((item, index) => {
    const playOnly = item.minutes <= 0 && item.playCount > 0
    const height = item.minutes > 0 ? Math.max(2.6, item.minutes / maxMinutes * 70) : (playOnly ? 1.7 : 0)
    const x = index * slotWidth + gap / 2
    return {
      ...item,
      index,
      visible: height > 0,
      playOnly,
      x: Number(x.toFixed(3)),
      y: Number((90 - height).toFixed(3)),
      width: Number(width.toFixed(3)),
      height: Number(height.toFixed(3)),
      center: Number((x + width / 2).toFixed(3))
    }
  })
})
const selectedTrend = computed(() => {
  const bins = trendBins.value
  if (!bins.length) return { label: '', minutes: 0, playCount: 0, index: -1 }
  if (selectedTrendIndex.value >= 0 && bins[selectedTrendIndex.value]) return bins[selectedTrendIndex.value]
  return [...bins].reverse().find(bin => bin.minutes > 0 || bin.playCount > 0) || bins[bins.length - 1]
})
const trendPeakMinutes = computed(() => Math.max(0, ...trendBins.value.map(bin => bin.minutes)))
const activeTrendBinCount = computed(() => trendBins.value.filter(bin => bin.minutes > 0 || bin.playCount > 0).length)
const trendGridLines = Object.freeze([18, 42, 66, 90])
const trendAxisTicks = computed(() => {
  const bins = trendBins.value
  if (!bins.length) return []
  const desiredTickCount = trendGranularity.value === 'month' ? 5 : 3
  const indexes = bins.length <= desiredTickCount
    ? bins.map((_, index) => index)
    : Array.from({ length: desiredTickCount }, (_, index) => Math.round(index * (bins.length - 1) / (desiredTickCount - 1)))
  return [...new Set(indexes)].map(index => {
    const bin = bins[index]
    return { key: bin.key, center: bin.center, shortLabel: trendGranularity.value === 'month' ? bin.label : bin.startLabel }
  })
})
const maxHourValue = computed(() => Math.max(1, ...asArray(activity.value.hourDistribution).map(item => Number(item.value || 0))))
const maxWeekdayValue = computed(() => Math.max(1, ...asArray(activity.value.weekdayDistribution).map(item => Number(item.value || 0))))
const completionRingStyle = computed(() => ({ '--completion': `${clampPercent(overview.value.completionRate)}%` }))

function asArray(value) {
  return Array.isArray(value) ? value : []
}

function clampPercent(value) {
  const number = Number(value || 0)
  return Math.max(0, Math.min(100, Number.isFinite(number) ? number : 0))
}

function formatNumber(value) {
  return Math.max(0, Number(value || 0)).toLocaleString('zh-CN', { maximumFractionDigits: 0 })
}

function formatDecimal(value) {
  return Math.max(0, Number(value || 0)).toLocaleString('zh-CN', { maximumFractionDigits: 1 })
}

function formatDate(value) {
  if (!value) return '最近播放'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '最近播放'
  return new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(date)
}

function formatUpdatedAt(value) {
  return new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(value)
}

function hourCellStyle(hour) {
  const ratio = Math.max(0.07, Number(hour.value || 0) / maxHourValue.value)
  return { '--hour-strength': ratio.toFixed(3) }
}

function weekdayBarStyle(day) {
  const ratio = Math.max(0, Number(day.value || 0) / maxWeekdayValue.value * 100)
  return { width: `${ratio}%` }
}

function selectTrendPoint(index) {
  selectedTrendIndex.value = index
}

function clearTrendSelection() {
  selectedTrendIndex.value = -1
}

function moveTrendSelection(direction) {
  const bins = trendBins.value
  if (!bins.length) return
  const currentIndex = selectedTrendIndex.value >= 0 ? selectedTrendIndex.value : selectedTrend.value.index
  const nextIndex = Math.max(0, Math.min(bins.length - 1, currentIndex + direction))
  selectTrendPoint(nextIndex)
}

async function selectRange(days) {
  if (displayDays.value === days || loading.value) return
  selectedTrendIndex.value = -1
  await loadStats(days)
}

async function loadStats(requestedDays = rangeDays.value) {
  if (loading.value) return
  loading.value = true
  error.value = ''
  // 并行加载 stats 与 pool count，各自独立失败（详见任务 A）
  const [statsResult, poolResult] = await Promise.allSettled([
    getStats({ days: requestedDays }),
    get('/pool/count')
  ])

  // stats 单独处理
  if (statsResult.status === 'fulfilled') {
    stats.value = statsResult.value
    rangeDays.value = Number(statsResult.value?.periodDays || requestedDays)
    lastUpdated.value = new Date()
  } else {
    stats.value = null
    error.value = statsResult.reason?.message || '加载统计数据失败，请稍后重试。'
  }

  // 虚拟片库数据量独立处理，stats 失败不影响
  if (poolResult.status === 'fulfilled') {
    poolCount.value = poolResult.value?.count || 0
  } else {
    poolCount.value = 0
  }

  loading.value = false
}

// —— 虚拟片库热度看板加载（独立于 stats，任一失败互不影响）——
async function loadTrendFor(poolId) {
  if (!poolId) return
  const requestId = ++trendRequestId.value
  poolTrendLoading.value = true
  try {
    const data = await getPoolHotness(poolId, { days: 30 })
    if (requestId !== trendRequestId.value) return // 过期请求丢弃
    poolTrend.value = Array.isArray(data?.items) ? data.items : []
  } catch {
    if (requestId !== trendRequestId.value) return
    poolTrend.value = []
  } finally {
    if (requestId === trendRequestId.value) poolTrendLoading.value = false
  }
}

async function loadHotness() {
  if (hotnessLoading.value) return
  hotnessLoading.value = true
  hotnessError.value = ''
  try {
    const data = await getTopHotness(TOP_HOTNESS_LIMIT)
    const items = Array.isArray(data?.items) ? data.items : []
    hotnessItems.value = items
    // 默认选中第一热门条目并加载其趋势；若榜单刷新后原选中仍在则保留
    const keep = items.find(item => item.poolId === selectedPoolId.value)
    const target = keep || items[0] || null
    selectedPoolId.value = target?.poolId || ''
    if (target) loadTrendFor(target.poolId)
  } catch (err) {
    hotnessError.value = err?.message || '热度榜加载失败，请稍后重试。'
  } finally {
    hotnessLoading.value = false
  }
}

function selectHotnessItem(item) {
  if (!item?.poolId || item.poolId === selectedPoolId.value) return
  selectedPoolId.value = item.poolId
  poolTrend.value = []
  loadTrendFor(item.poolId)
}

function openDetail(id) {
  if (!id) return
  router.push({ name: 'MovieDetail', params: { id } })
}

const categoryMap = { 电影: 'movie', 剧集: 'series', 动漫: 'anime', 音乐: 'music', 纪录: 'documentary' }

function isBrowsableCategory(label) {
  return Boolean(categoryMap[label])
}

function openCategory(label) {
  const category = categoryMap[label]
  if (!category) return
  router.push({ name: 'Home', query: { category } })
}

function resumeMovie(item) {
  if (!item?.id) return
  startPlay({
    movieId: item.id,
    movieTitle: item.title || '',
    episodeId: item.progress?.currentEpisodeId || item.currentEpisodeId || '',
    episodeTitle: item.progress?.currentEpisodeTitle || '',
    cover: historyCover(item),
    episodeList: [],
    seasonIndex: 0,
    position: Number(item.progress?.currentTime || item.currentTime || 0)
  })
}

function historyCover(item) {
  return item?.coverUrl || item?.cover || item?.posterUrl || item?.backdropUrl || ''
}

function initialOf(value) {
  return String(value || '影').trim().slice(0, 1) || '影'
}

function handleScanComplete() {
  loadStats()
}

onMounted(() => {
  loadStats()
  loadHotness()
  // 恢复上次生成的观影报告（零 LLM 成本），刷新后不再要求重新生成
  restoreLastReport()
  window.addEventListener('scan:completed', handleScanComplete)
})

onUnmounted(() => {
  window.removeEventListener('scan:completed', handleScanComplete)
})
</script>

<style scoped>
.stats-page {
  min-height: 100%;
  padding: 24px 32px 56px;
  color: var(--mp-text);
  background:
    radial-gradient(circle at 92% 2%, rgba(102, 126, 234, 0.2), transparent 29rem),
    radial-gradient(circle at 3% 18%, rgba(118, 75, 162, 0.14), transparent 23rem),
    var(--mp-bg);
}

.stats-hero,
.panel,
.snapshot-strip,
.state-card,
.notice-card {
  border: 1px solid var(--mp-line);
  background: var(--mp-panel);
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.14);
}

.stats-hero {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 28px;
  padding: 30px;
  border-radius: 18px;
  background:
    linear-gradient(118deg, rgba(118, 75, 162, 0.18), rgba(102, 126, 234, 0.08) 52%, transparent),
    var(--mp-panel-strong);
}

.eyebrow {
  display: block;
  color: var(--mp-text-muted);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.16em;
  line-height: 1.2;
}

.hero-copy h1,
.section-heading h2,
.panel-heading h2,
.panel-heading h3,
.profile-title-row h3 {
  margin: 0;
  color: var(--mp-text);
}

.hero-copy h1 {
  margin-top: 10px;
  font-size: clamp(30px, 3.2vw, 46px);
  letter-spacing: -0.05em;
  line-height: 1;
}

.hero-copy p,
.section-heading p,
.panel-heading p,
.profile-description,
.panel-footnote,
.state-card p {
  margin: 10px 0 0;
  color: var(--mp-text-soft);
  font-size: 13px;
  line-height: 1.7;
}

.hero-copy p { max-width: 590px; }

.hero-actions,
.range-switch,
.history-actions {
  display: flex;
  align-items: center;
  gap: 9px;
}

.range-switch {
  padding: 4px;
  border: 1px solid var(--mp-line);
  border-radius: 11px;
  background: rgba(0, 0, 0, 0.2);
}

.range-switch button,
.refresh-button,
.retry-button,
.notice-card button,
.history-actions button {
  border: 0;
  font: inherit;
  cursor: pointer;
}

.range-switch button {
  min-width: 47px;
  padding: 7px 9px;
  border-radius: 7px;
  color: var(--mp-text-soft);
  background: transparent;
  font-size: 12px;
  transition: 0.18s ease;
}

.range-switch button:hover,
.range-switch button.active {
  color: #fff;
  background: rgba(255, 255, 255, 0.13);
}

.refresh-button,
.retry-button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 38px;
  padding: 0 14px;
  border-radius: 10px;
  color: #fff;
  background: linear-gradient(135deg, var(--mp-gold), var(--mp-teal));
  font-weight: 700;
  font-size: 13px;
  transition: transform 0.18s ease, opacity 0.18s ease;
}

.refresh-button:hover:not(:disabled),
.retry-button:hover { transform: translateY(-1px); }
.refresh-button:disabled { cursor: wait; opacity: 0.65; }
.refresh-mark { display: inline-block; font-size: 18px; line-height: 1; }
.refresh-mark.spinning { animation: spin 0.8s linear infinite; }

.state-card,
.notice-card {
  margin-top: 18px;
  border-radius: 14px;
}

.state-card { padding: 30px; color: var(--mp-text-soft); text-align: center; }
.state-card strong { display: block; color: var(--mp-text); font-size: 17px; }
.error-card { border-color: rgba(240, 111, 92, 0.42); }
.retry-button { margin-top: 18px; }

.notice-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  padding: 11px 15px;
  border-color: rgba(240, 111, 92, 0.35);
  color: #ffd9d2;
  font-size: 13px;
}

.notice-card button { color: #fff; background: transparent; text-decoration: underline; }

.snapshot-strip {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr)) 1.8fr;
  gap: 0;
  margin-top: 18px;
  border-radius: 14px;
  overflow: hidden;
}

.snapshot-strip > div {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: baseline;
  gap: 2px 7px;
  min-height: 78px;
  padding: 15px 18px;
  border-right: 1px solid var(--mp-line);
}

.snapshot-strip span,
.snapshot-strip small { color: var(--mp-text-muted); font-size: 11px; }
.snapshot-strip span { grid-column: 1 / -1; }
.snapshot-strip strong { color: var(--mp-text); font-size: 24px; letter-spacing: -0.04em; }
.snapshot-strip small { padding-bottom: 2px; }

.snapshot-strip .pool-stat {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(118, 75, 162, 0.08));
}

.snapshot-strip .pool-stat strong {
  background: linear-gradient(135deg, #667eea, #764ba2);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.snapshot-note { align-self: center; margin: 0; padding: 15px 18px; color: var(--mp-text-soft); font-size: 12px; line-height: 1.65; }

.section-heading {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 16px;
  margin: 42px 0 16px;
}

.section-heading h2 { margin-top: 8px; font-size: 22px; letter-spacing: -0.03em; }
.section-heading p { margin-top: 5px; }
.updated-at { color: var(--mp-text-muted); font-size: 12px; white-space: nowrap; }
.compact-heading { margin-top: 40px; }

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.metric-card {
  min-height: 142px;
  padding: 18px;
  border: 1px solid var(--mp-line);
  border-radius: 14px;
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.055), rgba(255, 255, 255, 0.018));
}

.metric-card > span { display: block; color: var(--mp-text-soft); font-size: 13px; }
.metric-card strong { display: inline-block; margin-top: 14px; color: var(--mp-text); font-size: 34px; letter-spacing: -0.06em; line-height: 1; }
.metric-card small { margin-left: 5px; color: var(--mp-text-muted); font-size: 12px; }
.metric-card p { margin: 13px 0 0; color: var(--mp-text-muted); font-size: 12px; }
.accent-violet { box-shadow: inset 0 2px 0 #8e7cff; }
.accent-teal { box-shadow: inset 0 2px 0 #5fd5c5; }
.accent-coral { box-shadow: inset 0 2px 0 var(--mp-coral); }
.accent-gold { box-shadow: inset 0 2px 0 #d6a94c; }

.insight-grid,
.bottom-layout { display: grid; grid-template-columns: minmax(0, 1.45fr) minmax(300px, 0.8fr); gap: 14px; margin-top: 14px; }
.panel { min-width: 0; padding: 20px; border-radius: 16px; }
.panel-heading { display: flex; align-items: start; justify-content: space-between; gap: 14px; }
.panel-heading h2 { margin-top: 7px; font-size: 21px; }
.panel-heading h3 { font-size: 15px; letter-spacing: -0.015em; }
.panel-heading p { margin-top: 4px; font-size: 12px; }
.confidence { padding: 6px 8px; border-radius: 7px; color: #d8d0ff; background: rgba(142, 124, 255, 0.16); font-size: 11px; white-space: nowrap; }

.profile-empty { padding: 30px 0 8px; }
.profile-empty strong { font-size: 20px; }
.profile-empty p { max-width: 480px; color: var(--mp-text-soft); font-size: 13px; line-height: 1.7; }
.requirement-list,
.trait-list { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 17px; }
.requirement-list span,
.trait-list span { padding: 6px 9px; border: 1px solid var(--mp-line); border-radius: 999px; color: var(--mp-text-soft); background: rgba(255, 255, 255, 0.035); font-size: 11px; }

.profile-title-row { display: flex; align-items: center; gap: 14px; margin-top: 22px; }
.profile-code { display: grid; place-items: center; width: 58px; height: 58px; border-radius: 16px; color: #fff; background: linear-gradient(145deg, #8e7cff, #5a4ac1); font-weight: 900; letter-spacing: 0.08em; }
.profile-title-row h3 { font-size: 18px; }
.profile-title-row p { margin: 4px 0 0; color: var(--mp-text-soft); font-size: 13px; }
.profile-description { max-width: 660px; }
.dimension-list { display: grid; gap: 11px; margin-top: 20px; }
.dimension-row { display: grid; grid-template-columns: 68px minmax(60px, 1fr) 30px; align-items: center; gap: 9px; color: var(--mp-text-soft); font-size: 12px; }
.dimension-row strong { color: var(--mp-text); text-align: right; font-variant-numeric: tabular-nums; }
.dimension-track { height: 5px; border-radius: 99px; background: rgba(255, 255, 255, 0.1); overflow: hidden; }
.dimension-track i { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #7564e9, #a697ff); }

.rhythm-main { margin-top: 31px; }
.rhythm-main strong { display: block; color: var(--mp-text); font-size: 40px; letter-spacing: -0.06em; line-height: 1; }
.rhythm-main span { display: block; margin-top: 8px; color: var(--mp-text-soft); font-size: 13px; }
.rhythm-list { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 26px 0 0; }
.rhythm-list div { min-width: 0; padding: 10px 0 0; border-top: 1px solid var(--mp-line); }
.rhythm-list dt { color: var(--mp-text-muted); font-size: 11px; }
.rhythm-list dd { margin: 5px 0 0; color: var(--mp-text); font-size: 13px; white-space: nowrap; }
.panel-footnote { margin-top: 18px; font-size: 11px; }

/* AI 观影报告 */
.llm-report-section { margin-top: 14px; }
.report-source { padding: 6px 10px; border-radius: 999px; font-size: 11px; white-space: nowrap; }
.report-source.source-llm { color: #d8d0ff; background: rgba(142, 124, 255, 0.18); }
.report-source.source-template { color: var(--mp-text-soft); background: rgba(255, 255, 255, 0.07); }
.report-intro { padding: 14px 0 4px; }
.report-intro p { color: var(--mp-text-soft); font-size: 13px; line-height: 1.8; }
.report-generate-btn {
  margin-top: 14px;
  padding: 9px 18px;
  border: 0;
  border-radius: 10px;
  color: #fff;
  background: linear-gradient(135deg, #8e7cff, #5a4ac1);
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.18s ease, opacity 0.18s ease;
}
.report-generate-btn:hover { transform: translateY(-1px); }
.report-loading { padding: 34px 0; color: var(--mp-text-soft); font-size: 13px; text-align: center; }
.report-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 16px; }
.report-toolbar-right { display: flex; gap: 8px; }
.report-compare-btn {
  padding: 6px 14px;
  border: 1px solid var(--mp-line);
  border-radius: 8px;
  color: var(--mp-text-soft);
  background: transparent;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
  transition: 0.18s ease;
}
.report-compare-btn:hover:not(:disabled) { color: #fff; border-color: rgba(142, 124, 255, 0.6); }
.report-compare-btn.active { color: #fff; background: rgba(142, 124, 255, 0.25); border-color: rgba(142, 124, 255, 0.6); }

.report-compare { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 14px; }
.compare-col { min-width: 0; }
.compare-label { display: inline-block; margin-bottom: 8px; padding: 4px 10px; border-radius: 999px; font-size: 11px; font-weight: 700; }
.compare-label.source-llm { color: #d8d0ff; background: rgba(142, 124, 255, 0.18); }
.compare-label.source-template { color: var(--mp-text-soft); background: rgba(255, 255, 255, 0.07); }
.report-days-switch { display: inline-flex; padding: 3px; border: 1px solid var(--mp-line); border-radius: 9px; background: rgba(255, 255, 255, 0.04); }
.report-days-switch button {
  padding: 5px 12px;
  border: 0;
  border-radius: 6px;
  color: var(--mp-text-soft);
  background: transparent;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
  transition: 0.18s ease;
}
.report-days-switch button:hover,
.report-days-switch button.active { color: #fff; background: rgba(142, 124, 255, 0.35); }
.report-regenerate-btn {
  padding: 6px 14px;
  border: 1px solid var(--mp-line);
  border-radius: 8px;
  color: var(--mp-text-soft);
  background: transparent;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
  transition: 0.18s ease;
}
.report-regenerate-btn:hover:not(:disabled) { color: #fff; border-color: rgba(142, 124, 255, 0.6); }
.report-regenerate-btn:disabled { cursor: wait; opacity: 0.6; }
.report-message { margin-top: 14px; padding: 9px 12px; border-radius: 8px; color: #e7c98f; background: rgba(231, 201, 143, 0.08); font-size: 12px; line-height: 1.6; }
.report-stale { color: #f0a56a; background: rgba(240, 165, 106, 0.08); }
.report-empty { margin-top: 16px; padding: 24px 0; color: var(--mp-text-soft); font-size: 13px; text-align: center; }
.report-markdown { margin-top: 14px; color: var(--mp-text); font-size: 13.5px; line-height: 1.85; }
.report-markdown :deep(h3) { margin: 18px 0 8px; font-size: 15px; }
.report-markdown :deep(h4) { margin: 14px 0 6px; font-size: 13.5px; color: var(--mp-text); }
.report-markdown :deep(h3:first-child),
.report-markdown :deep(h4:first-child) { margin-top: 0; }
.report-markdown :deep(p) { margin: 7px 0; color: var(--mp-text-soft); }
.report-markdown :deep(ul),
.report-markdown :deep(ol) { margin: 8px 0; padding-left: 20px; color: var(--mp-text-soft); }
.report-markdown :deep(li) { margin: 4px 0; }
.report-markdown :deep(strong) { color: var(--mp-text); font-weight: 700; }
.report-markdown :deep(code) { padding: 1px 6px; border-radius: 5px; background: rgba(255, 255, 255, 0.08); font-size: 12px; }
.report-footnote { color: var(--mp-text-muted); }

.activity-layout { display: grid; grid-template-columns: minmax(0, 1.52fr) minmax(240px, 0.83fr); gap: 14px; }
.trend-panel { grid-row: span 2; }
.panel-value { display: inline-grid; grid-template-columns: auto auto; align-items: baseline; column-gap: 4px; color: var(--mp-text); font-size: 28px; font-variant-numeric: tabular-nums; letter-spacing: -0.06em; line-height: 1; white-space: nowrap; }
.panel-value small { grid-column: 1 / -1; margin: 0 0 5px; color: var(--mp-text-muted); font-size: 10px; font-weight: 700; letter-spacing: 0.12em; }
.panel-value em { color: var(--mp-text-muted); font-size: 11px; font-style: normal; letter-spacing: 0; }
.trend-chart { height: 260px; margin-top: 19px; }
.trend-chart svg { display: block; width: 100%; height: calc(100% - 47px); overflow: visible; }
.trend-grid line { stroke: rgba(255, 255, 255, 0.075); stroke-width: 0.55; vector-effect: non-scaling-stroke; }
.trend-grid line:last-child { stroke: rgba(255, 255, 255, 0.16); }
.trend-selection { fill: rgba(142, 124, 255, 0.12); }
.trend-bar { fill: url(#trend-bar-fill); transform-origin: center bottom; transition: opacity 0.18s ease, filter 0.18s ease; }
.trend-bar.selected { filter: brightness(1.3); }
.trend-bar.play-only { fill: rgba(194, 183, 255, 0.5); }
.trend-hit-area { fill: transparent; cursor: pointer; pointer-events: all; }
.trend-chart:focus { outline: 1px solid rgba(196, 186, 255, 0.7); outline-offset: 5px; border-radius: 4px; }
.trend-axis { position: relative; height: 17px; margin-top: 3px; color: var(--mp-text-muted); font-size: 10px; }
.trend-axis span { position: absolute; transform: translateX(-50%); white-space: nowrap; }
.trend-context { display: flex; justify-content: space-between; gap: 12px; margin-top: 8px; color: var(--mp-text-muted); font-size: 10px; }
.chart-empty { display: grid; min-height: 142px; place-items: center; color: var(--mp-text-muted); text-align: center; font-size: 13px; }

.hour-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 6px; margin-top: 21px; }
.hour-cell { min-height: 54px; padding: 5px; border: 1px solid rgba(142, 124, 255, calc(var(--hour-strength) * 0.55)); border-radius: 8px; color: var(--mp-text-soft); background: rgba(142, 124, 255, calc(var(--hour-strength) * 0.52)); font: inherit; cursor: default; text-align: left; }
.hour-cell span { display: block; font-size: 10px; }
.hour-cell b { display: block; margin-top: 8px; color: var(--mp-text); font-size: 13px; }

.weekday-list { display: grid; gap: 11px; margin-top: 22px; }
.weekday-row { display: grid; grid-template-columns: 26px minmax(40px, 1fr) 18px; align-items: center; gap: 8px; color: var(--mp-text-soft); font-size: 11px; }
.weekday-row > div { height: 7px; border-radius: 99px; background: rgba(255, 255, 255, 0.1); overflow: hidden; }
.weekday-row i { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #5fd5c5, #9eeadc); }
.weekday-row b { color: var(--mp-text); text-align: right; font-size: 12px; }

.library-layout { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(220px, 0.8fr) minmax(190px, 0.62fr); gap: 14px; }
.distribution-list { display: grid; gap: 9px; margin-top: 20px; }
.distribution-row { display: grid; grid-template-columns: 58px minmax(45px, 1fr) 26px; align-items: center; gap: 8px; width: 100%; padding: 0; border: 0; color: var(--mp-text-soft); background: transparent; font: inherit; text-align: left; cursor: pointer; }
.distribution-row:hover span,
.distribution-row:hover strong { color: #fff; }
.distribution-row.disabled { cursor: default; opacity: 0.62; }
.distribution-row.disabled:hover span,
.distribution-row.disabled:hover strong { color: inherit; }
.distribution-row > span { font-size: 12px; }
.distribution-row > div { height: 7px; overflow: hidden; border-radius: 99px; background: rgba(255, 255, 255, 0.1); }
.distribution-row i { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, var(--mp-gold), var(--mp-teal)); }
.distribution-row strong { color: var(--mp-text); font-size: 12px; text-align: right; }

.completion-content { display: flex; align-items: center; justify-content: space-around; gap: 20px; min-height: 144px; }
.completion-ring { display: grid; place-items: center; width: 122px; aspect-ratio: 1; border-radius: 50%; background: conic-gradient(#8e7cff var(--completion), rgba(255, 255, 255, 0.1) 0); }
.completion-ring > div { display: grid; place-items: center; width: 98px; aspect-ratio: 1; border-radius: 50%; background: #111318; }
.completion-ring strong { font-size: 20px; letter-spacing: -0.06em; }
.completion-ring span { margin-top: -10px; color: var(--mp-text-muted); font-size: 11px; }
.completion-content dl { display: grid; gap: 10px; margin: 0; min-width: 78px; }
.completion-content dl div { display: flex; justify-content: space-between; gap: 8px; }
.completion-content dt { color: var(--mp-text-muted); font-size: 11px; }
.completion-content dd { margin: 0; color: var(--mp-text); font-size: 13px; }

.source-list { display: grid; gap: 9px; margin-top: 20px; }
.source-list div { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 0; border-bottom: 1px solid rgba(255, 255, 255, 0.07); color: var(--mp-text-soft); font-size: 12px; }
.source-list div:last-child { border-bottom: 0; }
.source-list b { color: var(--mp-text); font-size: 13px; }
.tag-summary { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--mp-line); }
.tag-summary-title { width: 100%; margin-bottom: 2px; color: var(--mp-text-muted); font-size: 11px; }
.tag-chip { padding: 4px 7px; border-radius: 999px; color: var(--mp-text-soft); background: rgba(255, 255, 255, 0.06); font-size: 10px; }
.tag-chip b { margin-left: 3px; color: var(--mp-text); font-size: inherit; }

.bottom-layout { margin-top: 40px; }
.title-list,
.history-list { display: grid; gap: 2px; margin-top: 17px; }
.title-row { display: grid; grid-template-columns: 29px 38px minmax(0, 1fr) 16px; align-items: center; gap: 10px; width: 100%; min-height: 58px; padding: 7px 0; border: 0; border-bottom: 1px solid rgba(255, 255, 255, 0.06); color: inherit; background: transparent; text-align: left; cursor: pointer; }
.title-row:last-child { border-bottom: 0; }
.title-row:hover .title-copy strong,
.title-row:hover .row-arrow { color: #fff; }
.title-row.disabled { cursor: default; opacity: 0.64; }
.title-row.disabled:hover .title-copy strong,
.title-row.disabled:hover .row-arrow { color: inherit; }
.title-rank { color: var(--mp-text-muted); font-size: 11px; font-variant-numeric: tabular-nums; }
.title-row img,
.title-cover-placeholder,
.history-row img,
.history-cover-placeholder { width: 38px; height: 46px; border-radius: 6px; object-fit: cover; background: linear-gradient(145deg, #413d65, #252333); }
.title-cover-placeholder,
.history-cover-placeholder { display: grid; place-items: center; color: #e5e1ff; font-size: 15px; }
.title-copy,
.history-copy { min-width: 0; }
.title-copy strong,
.history-copy strong { display: block; overflow: hidden; color: var(--mp-text); font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.title-copy small,
.history-copy > span { display: block; overflow: hidden; margin-top: 4px; color: var(--mp-text-muted); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.row-arrow { color: var(--mp-text-muted); font-size: 25px; line-height: 1; }

.history-row { display: grid; grid-template-columns: 38px minmax(0, 1fr) auto; align-items: center; gap: 10px; min-height: 63px; padding: 7px 0; border-bottom: 1px solid rgba(255, 255, 255, 0.06); }
.history-row:last-child { border-bottom: 0; }
.history-copy i { display: block; height: 4px; margin-top: 7px; overflow: hidden; border-radius: 99px; background: rgba(255, 255, 255, 0.1); }
.history-copy i b { display: block; height: 100%; border-radius: inherit; background: #8e7cff; }
.history-actions { gap: 5px; }
.history-actions button { padding: 5px 6px; border-radius: 6px; color: var(--mp-text-soft); background: rgba(255, 255, 255, 0.07); font-size: 11px; }
.history-actions .play-action { color: #fff; background: rgba(142, 124, 255, 0.7); }

@keyframes spin { to { transform: rotate(360deg); } }

/* —— 虚拟片库外部热度看板（任务 C）—— */
.hotness-section { margin-top: 46px; }
.hotness-heading { margin-top: 0; }
.hotness-layout { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(290px, 0.9fr); gap: 14px; margin-top: 14px; align-items: stretch; }
.hotness-top-list { display: flex; flex-direction: column; gap: 3px; margin-top: 10px; }
.hotness-row { display: grid; grid-template-columns: 24px 40px minmax(0, 1fr) auto; align-items: center; gap: 12px; width: 100%; padding: 6px 10px; border: 1px solid transparent; border-left: 2px solid transparent; border-radius: 12px; background: transparent; text-align: left; cursor: pointer; transition: background 0.15s ease, border-color 0.15s ease; }
.hotness-row:hover { background: rgba(255, 255, 255, 0.05); }
.hotness-row.active { border-color: rgba(246, 180, 92, 0.22); border-left-color: var(--mp-gold, #f6b45c); background: linear-gradient(90deg, rgba(246, 180, 92, 0.1), rgba(255, 255, 255, 0.02)); }
.hotness-rank { color: var(--mp-text-muted); font-size: 13px; font-weight: 700; text-align: center; letter-spacing: -0.02em; }
.hotness-row.active .hotness-rank { color: #f6b45c; }
.hotness-row img { width: 40px; height: 60px; object-fit: cover; border-radius: 6px; background: rgba(255, 255, 255, 0.06); }
.hotness-cover-placeholder { display: flex; align-items: center; justify-content: center; width: 40px; height: 60px; border-radius: 6px; color: var(--mp-text-muted); font-size: 17px; font-weight: 700; background: linear-gradient(135deg, rgba(246, 180, 92, 0.22), rgba(255, 255, 255, 0.06)); }
.hotness-copy { min-width: 0; }
.hotness-copy strong { display: block; overflow: hidden; color: var(--mp-text); font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.hotness-copy small { display: block; overflow: hidden; margin-top: 3px; color: var(--mp-text-muted); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.hotness-bar { display: block; height: 4px; margin-top: 7px; overflow: hidden; border-radius: 99px; background: rgba(255, 255, 255, 0.09); }
.hotness-bar b { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #f6b45c, #e8903c); }
.hotness-pop { min-width: 54px; color: #f6b45c; font-size: 12px; font-weight: 700; text-align: right; font-variant-numeric: tabular-nums; }
.heat-trend-chart { margin-top: 12px; }
.heat-trend-chart svg { display: block; width: 100%; height: 190px; }
.heat-trend-chart .trend-axis { margin-top: 6px; }

@media (max-width: 1160px) {
  .snapshot-strip { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .snapshot-note { grid-column: 1 / -1; border-top: 1px solid var(--mp-line); }
  .library-layout { grid-template-columns: minmax(0, 1fr) minmax(220px, 0.8fr); }
  .source-panel { grid-column: 1 / -1; }
  .source-list { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
}

@media (max-width: 900px) {
  .stats-page { padding: 20px 20px 42px; }
  .stats-hero { align-items: start; flex-direction: column; }
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .insight-grid,
  .bottom-layout,
  .activity-layout,
  .hotness-layout { grid-template-columns: 1fr; }
  .trend-panel { grid-row: auto; }
  .library-layout { grid-template-columns: 1fr 1fr; }
}

@media (max-width: 620px) {
  .stats-page { padding: 14px 12px 34px; }
  .stats-hero { padding: 22px 18px; border-radius: 14px; }
  .hero-actions { align-items: stretch; flex-direction: column; width: 100%; }
  .range-switch { width: 100%; justify-content: space-between; }
  .range-switch button { flex: 1; }
  .refresh-button { justify-content: center; }
  .snapshot-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .snapshot-strip > div:nth-child(2) { border-right: 0; }
  .snapshot-strip > div:nth-child(-n + 2) { border-bottom: 1px solid var(--mp-line); }
  .snapshot-note { grid-column: 1 / -1; }
  .section-heading { align-items: start; flex-direction: column; margin-top: 30px; }
  .metric-grid,
  .library-layout { grid-template-columns: 1fr; }
  .metric-card { min-height: 126px; }
  .panel { padding: 17px; border-radius: 13px; }
  .rhythm-list { grid-template-columns: 1fr; gap: 8px; }
  .rhythm-list div { display: flex; justify-content: space-between; align-items: baseline; }
  .hour-grid { grid-template-columns: repeat(4, 1fr); }
  .source-panel { grid-column: auto; }
  .source-list { grid-template-columns: 1fr; }
  .completion-content { justify-content: start; }
  .history-actions { align-items: end; flex-direction: column; }
  .history-actions button { min-width: 38px; }
  .hotness-row { grid-template-columns: 18px 36px minmax(0, 1fr); gap: 9px; }
  .hotness-row img,
  .hotness-cover-placeholder { width: 36px; height: 54px; }
  .hotness-pop { display: none; }
}
</style>
