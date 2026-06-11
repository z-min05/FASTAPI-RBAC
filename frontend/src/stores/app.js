import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const collapsed = ref(false)
  const breadcrumbs = ref([])

  function toggleCollapsed() {
    collapsed.value = !collapsed.value
  }

  function setBreadcrumbs(items) {
    breadcrumbs.value = items
  }

  return { collapsed, breadcrumbs, toggleCollapsed, setBreadcrumbs }
})
