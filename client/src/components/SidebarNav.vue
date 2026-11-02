<template>
  <aside :class="['sidebar', { collapsed: isCollapsed }]">
    <button
      type="button"
      class="sidebar-toggle"
      :aria-expanded="String(!isCollapsed)"
      :aria-label="isCollapsed ? t('nav.expand') : t('nav.collapse')"
      :title="isCollapsed ? t('nav.expand') : t('nav.collapse')"
      @click="toggle"
    >
      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <rect x="3" y="4" width="18" height="16" rx="2" />
        <line x1="9" y1="4" x2="9" y2="20" />
        <!-- chevron points toward the direction the sidebar will move -->
        <polyline v-if="isCollapsed" points="13 9 16 12 13 15" />
        <polyline v-else points="16 9 13 12 16 15" />
      </svg>
    </button>

    <nav class="sidebar-links" aria-label="Main navigation">
      <router-link
        v-for="link in links"
        :key="link.to"
        :to="link.to"
        :class="['sidebar-link', { active: $route.path === link.to }]"
        :title="t(link.label)"
        :aria-label="t(link.label)"
      >
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <g v-html="link.icon" />
        </svg>
        <span class="sidebar-label">{{ t(link.label) }}</span>
      </router-link>
    </nav>
  </aside>
</template>

<script>
import { onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from '../composables/useI18n'
import { useSidebar } from '../composables/useSidebar'

// Icon paths are static constants defined here (never user input), so injecting
// them with v-html is safe. Keeping them as data avoids seven near-identical
// <svg> blocks in the template.
const links = [
  {
    to: '/',
    label: 'nav.overview',
    icon: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>'
  },
  {
    to: '/inventory',
    label: 'nav.inventory',
    icon: '<path d="M21 8l-9-5-9 5v8l9 5 9-5z"/><polyline points="3 8 12 13 21 8"/><line x1="12" y1="13" x2="12" y2="21"/>'
  },
  {
    to: '/orders',
    label: 'nav.orders',
    icon: '<path d="M9 4h6a1 1 0 0 1 1 1v1H8V5a1 1 0 0 1 1-1z"/><path d="M8 5H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><line x1="8" y1="12" x2="16" y2="12"/><line x1="8" y1="16" x2="13" y2="16"/>'
  },
  {
    to: '/spending',
    label: 'nav.finance',
    icon: '<circle cx="12" cy="12" r="9"/><path d="M14.5 9.5c-.5-1-1.5-1.5-2.5-1.5-1.4 0-2.5.8-2.5 2s1.1 1.7 2.5 2 2.5.8 2.5 2-1.1 2-2.5 2c-1 0-2-.5-2.5-1.5"/><line x1="12" y1="6.5" x2="12" y2="8"/><line x1="12" y1="16" x2="12" y2="17.5"/>'
  },
  {
    to: '/demand',
    label: 'nav.demandForecast',
    icon: '<polyline points="3 17 9 11 13 15 21 7"/><polyline points="15 7 21 7 21 13"/>'
  },
  {
    to: '/restocking',
    label: 'nav.restocking',
    icon: '<polyline points="21 12 21 7 16 7"/><path d="M21 7a9 9 0 0 0-15.5-2.5L3 7"/><polyline points="3 12 3 17 8 17"/><path d="M3 17a9 9 0 0 0 15.5 2.5L21 17"/>'
  },
  {
    to: '/reports',
    label: 'nav.reports',
    icon: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><polyline points="14 3 14 8 19 8"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="15" y2="17"/>'
  }
]

export default {
  name: 'SidebarNav',
  setup() {
    const { t } = useI18n()
    const { isCollapsed, toggle, startWatching, stopWatching } = useSidebar()

    onMounted(startWatching)
    onBeforeUnmount(stopWatching)

    return { t, links, isCollapsed, toggle }
  }
}
</script>

<style scoped>
.sidebar {
  flex-shrink: 0;
  width: 220px;
  /* Pinned below the 70px sticky top bar and scrolls independently if short */
  position: sticky;
  top: 70px;
  height: calc(100vh - 70px);
  overflow-y: auto;
  overflow-x: hidden;
  background: #ffffff;
  border-right: 1px solid #e2e8f0;
  padding: 0.75rem;
  transition: width 0.2s ease;
}

.sidebar.collapsed {
  width: 64px;
  padding: 0.75rem 0.5rem;
}

.sidebar-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  margin-bottom: 0.5rem;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease;
}

.sidebar-toggle:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.sidebar-toggle:focus-visible,
.sidebar-link:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: 2px;
}

.sidebar-links {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.sidebar-link {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  height: 40px;
  padding: 0 0.625rem;
  border-radius: 6px;
  color: #64748b;
  text-decoration: none;
  font-size: 0.938rem;
  font-weight: 500;
  white-space: nowrap;
  transition: background 0.2s ease, color 0.2s ease;
}

.sidebar-link svg {
  flex-shrink: 0;
}

.sidebar-link:hover {
  color: #0f172a;
  background: #f1f5f9;
}

.sidebar-link.active {
  color: #2563eb;
  background: #eff6ff;
}

/* Labels are hidden in icons-only mode. display:none also drops them from the
   accessibility tree, so each link's aria-label and title keep it identifiable. */
.sidebar.collapsed .sidebar-label {
  display: none;
}

.sidebar.collapsed .sidebar-link {
  justify-content: center;
  padding: 0;
}
</style>
