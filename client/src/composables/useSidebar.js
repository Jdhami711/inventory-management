import { ref, computed } from 'vue'

const STORAGE_KEY = 'sidebar-collapsed'
const WIDE_QUERY = '(min-width: 1024px)'

// Read a previously stored manual choice. Returns true/false, or null when the
// user has never toggled (so the screen width decides).
const readStoredChoice = () => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'true') return true
    if (stored === 'false') return false
  } catch (e) {
    // localStorage can throw (private mode, blocked storage); fall back to auto
  }
  return null
}

// Shared state (singleton pattern, same as useFilters)
const manualChoice = ref(readStoredChoice())   // true = collapsed, false = expanded, null = auto
// Read the width synchronously at load so a narrow screen never renders one
// expanded frame before the media query listener attaches on mount.
const isWideScreen = ref(
  typeof window !== 'undefined' && window.matchMedia
    ? window.matchMedia(WIDE_QUERY).matches
    : true
)

let mediaQuery = null
let mediaListener = null
let subscribers = 0

export function useSidebar() {
  // A stored manual choice always wins. Otherwise collapse below 1024px.
  const isCollapsed = computed(() => {
    if (manualChoice.value !== null) return manualChoice.value
    return !isWideScreen.value
  })

  const toggle = () => {
    manualChoice.value = !isCollapsed.value
    try {
      localStorage.setItem(STORAGE_KEY, String(manualChoice.value))
    } catch (e) {
      // Persisting is best-effort; the in-memory choice still applies
    }
  }

  // Start tracking the screen width. Reference counted because the state is
  // shared: the listener is only attached once and removed with the last user.
  const startWatching = () => {
    subscribers++
    if (mediaQuery || typeof window === 'undefined' || !window.matchMedia) return

    mediaQuery = window.matchMedia(WIDE_QUERY)
    isWideScreen.value = mediaQuery.matches
    mediaListener = (event) => { isWideScreen.value = event.matches }
    mediaQuery.addEventListener('change', mediaListener)
  }

  const stopWatching = () => {
    subscribers = Math.max(0, subscribers - 1)
    if (subscribers > 0 || !mediaQuery) return

    mediaQuery.removeEventListener('change', mediaListener)
    mediaQuery = null
    mediaListener = null
  }

  return {
    isCollapsed,
    toggle,
    startWatching,
    stopWatching
  }
}
