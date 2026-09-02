import { useAuthStore } from '@/stores/auth'

/**
 * 检查当前用户是否拥有指定按钮权限
 * @param {string} code - 按钮权限编码，如 'user:create'
 * @returns {boolean}
 */
export function hasButtonPermission(code) {
  const authStore = useAuthStore()
  if (authStore.userInfo?.is_superuser) return true
  return (authStore.buttonPermissions || []).includes(code)
}

/**
 * 检查当前用户是否拥有指定 API 权限
 * @param {string} code - API 权限编码，如 'user:list'
 * @returns {boolean}
 */
export function hasApiPermission(code) {
  const authStore = useAuthStore()
  if (authStore.userInfo?.is_superuser) return true
  return (authStore.apiPermissions || []).includes(code)
}

/**
 * 检查当前用户是否拥有任意一个指定权限
 * @param {string[]} codes - 权限编码数组
 * @returns {boolean}
 */
export function hasAnyPermission(codes) {
  return codes.some(code => hasButtonPermission(code) || hasApiPermission(code))
}
