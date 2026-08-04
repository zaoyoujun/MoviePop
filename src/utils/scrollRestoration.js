/**
 * Restore scroll positions for pages rendered inside Naive UI n-layout-content.
 * The app scrolls the layout container, not window, so window.scrollY is always
 * the wrong source for list pages.
 */

const CONTENT_SCROLL_SELECTORS = [
  '.content-layout .n-layout-scroll-container',
  '.content-layout .n-scrollbar-container'
]

const inMemoryPositions = new Map()
const restoreJobs = new Map()

export function getContentScrollElement() {
  const containers = CONTENT_SCROLL_SELECTORS
    .map(selector => document.querySelector(selector))
    .filter(Boolean)
  return containers.find(element => element.scrollTop > 0 || element.scrollHeight > element.clientHeight)
    || containers[0]
    || document.scrollingElement
    || document.documentElement
}

export function saveScrollPosition(storageKey) {
  const element = getContentScrollElement()
  const data = {
    scrollTop: element?.scrollTop || 0,
    savedAt: Date.now()
  }
  inMemoryPositions.set(storageKey, data)
  try {
    sessionStorage.setItem(storageKey, JSON.stringify(data))
  } catch {
    // Electron normally allows sessionStorage, but retaining an in-memory
    // value still preserves the position for the current app session.
  }
}

export function readScrollPosition(storageKey) {
  const inMemory = inMemoryPositions.get(storageKey)
  if (inMemory && Number.isFinite(Number(inMemory.scrollTop))) {
    return Number(inMemory.scrollTop)
  }

  let raw = null
  try {
    raw = sessionStorage.getItem(storageKey)
  } catch {
    return null
  }
  if (!raw) return null

  try {
    const data = JSON.parse(raw)
    const scrollTop = Number(data?.scrollTop || 0)
    return Number.isFinite(scrollTop) ? scrollTop : null
  } catch {
    return null
  }
}

export function restoreScrollPosition(storageKey) {
  const scrollTop = readScrollPosition(storageKey)
  if (scrollTop === null) return false

  const element = getContentScrollElement()
  if (!element) return false

  element.scrollTop = scrollTop
  return Math.abs(element.scrollTop - scrollTop) < 1
}

export function trackScrollPosition(storageKey) {
  const element = getContentScrollElement()
  if (!element) return () => {}

  let frameId = 0
  const onScroll = () => {
    if (frameId) return
    frameId = requestAnimationFrame(() => {
      frameId = 0
      saveScrollPosition(storageKey)
    })
  }
  element.addEventListener('scroll', onScroll, { passive: true })

  return () => {
    element.removeEventListener('scroll', onScroll)
    if (frameId) cancelAnimationFrame(frameId)
  }
}

export function scheduleScrollRestore(storageKey, attempts = 24) {
  restoreJobs.get(storageKey)?.()

  const target = readScrollPosition(storageKey)
  if (target === null) return () => {}

  let count = 0
  let frameId = 0
  let timerId = 0
  let cancelled = false

  const cancel = () => {
    cancelled = true
    if (frameId) cancelAnimationFrame(frameId)
    if (timerId) clearTimeout(timerId)
    if (restoreJobs.get(storageKey) === cancel) restoreJobs.delete(storageKey)
  }
  restoreJobs.set(storageKey, cancel)

  const run = () => {
    if (cancelled) return

    const restored = restoreScrollPosition(storageKey)
    count += 1

    // The layout is recreated after returning from MovieDetail.  If its
    // content has not finished rendering yet, assigning scrollTop is clamped
    // to zero. Retry with a small backoff until it can reach the saved offset.
    if (!restored && count < attempts) {
      timerId = window.setTimeout(() => {
        frameId = requestAnimationFrame(run)
      }, Math.min(240, 24 * count))
      return
    }

    cancel()
  }

  frameId = requestAnimationFrame(run)
  return cancel
}
