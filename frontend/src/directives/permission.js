import { hasButtonPermission } from '@/utils/permission'

/**
 * v-permission 指令
 * 用法: v-permission="'user:create'" 或 v-permission="['user:create', 'user:update']"
 * 如果用户没有对应按钮权限，则移除该 DOM 元素
 */
export const permissionDirective = {
  mounted(el, binding) {
    const { value } = binding
    if (!value) return

    const codes = Array.isArray(value) ? value : [value]
    const hasPermission = codes.some(code => hasButtonPermission(code))

    if (!hasPermission) {
      el.parentNode && el.parentNode.removeChild(el)
    }
  },
}

/**
 * v-role 指令
 * 用法: v-role="'admin'" 或 v-role="['admin', 'editor']"
 * 如果用户没有对应角色，则移除该 DOM 元素（保留作为扩展）
 */
export const roleDirective = {
  mounted(el, binding) {
    // 预留角色指令
  },
}

export default {
  install(app) {
    app.directive('permission', permissionDirective)
    app.directive('role', roleDirective)
  },
}
