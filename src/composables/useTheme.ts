import { useAppStore } from '../stores/app'

export function useTheme() {
  const store = useAppStore()

  function setTheme(theme: string) {
    store.setTheme(theme)
  }

  return { theme: store.theme, setTheme }
}
