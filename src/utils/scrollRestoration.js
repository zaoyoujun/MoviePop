/**
 * Restore scroll positions for pages rendered inside Naive UI n-layout-content.
 * The app scrolls the layout container, not window, so window.scrollY is always
 * the wrong source for list pages.
 */

const CONTENT_SCROLL_SELECTOR = '.content-layout .n-layout-scroll-container'

export function getContentScrollElement() {
  return document.querySelector(CONTENT_SCROLL_SELECTOR) || document.scrollingElement || document.documentElement
}

export function saveScrollPosition(storageKey) {
  const element = getContentScrollElement()
  sessionStorage.setItem(storageKey, JSON.stringify({
    scrollTop: element?.scrollTop || 0,
    savedAt: Date.now()
  }))
}

export function readScrollPosition(storageKey) {
  const raw = sessionStorage.getItem(storageKey)
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
  return true
}

export function scheduleScrollRestore(storageKey, attempts = 8) {
  let count = 0

  const run = () => {
    restoreScrollPosition(storageKey)
    count += 1

    if (count < attempts) {
      requestAnimationFrame(run)
    }
  }

  requestAnimationFrame(run)
}
