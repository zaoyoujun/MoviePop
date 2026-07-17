/** Runtime flags shared by the renderer. */
const viteTestMode = ['1', 'true'].includes(String(import.meta.env.VITE_TEST_MODE || '').toLowerCase())
const electronTestMode = Boolean(window.electronAPI?.isTestMode?.())

export const isTestMode = viteTestMode || electronTestMode
