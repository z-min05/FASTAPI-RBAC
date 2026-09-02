import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/pages/Login.vue'),
    meta: { title: '登录', requiresAuth: false }
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/dashboard',
    meta: { requiresAuth: true },
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/pages/Dashboard.vue'),
        meta: { title: '仪表盘', icon: 'DashboardOutlined' }
      },
      {
        path: 'system/users',
        name: 'UserManage',
        component: () => import('@/pages/UserManage.vue'),
        meta: { title: '用户管理', icon: 'UserOutlined' }
      },
      {
        path: 'system/roles',
        name: 'RoleManage',
        component: () => import('@/pages/RoleManage.vue'),
        meta: { title: '角色管理', icon: 'TeamOutlined' }
      },
      {
        path: 'system/permissions',
        name: 'PermissionManage',
        component: () => import('@/pages/PermissionManage.vue'),
        meta: { title: '权限管理', icon: 'SafetyOutlined' }
      },
      {
        path: 'system/menus',
        name: 'MenuManage',
        component: () => import('@/pages/MenuManage.vue'),
        meta: { title: '菜单管理', icon: 'MenuOutlined' }
      },
      {
        path: 'system/departments',
        name: 'DepartmentManage',
        component: () => import('@/pages/DepartmentManage.vue'),
        meta: { title: '部门管理', icon: 'ApartmentOutlined' }
      },
      {
        path: 'system/logs',
        name: 'LogManage',
        component: () => import('@/pages/LogManage.vue'),
        meta: { title: '操作日志', icon: 'FileTextOutlined' }
      },
      {
        path: 'test/projects',
        name: 'ProjectManage',
        component: () => import('@/pages/test/ProjectManage.vue'),
        meta: { title: '项目管理', icon: 'FolderOutlined' }
      },
      {
        path: 'test/testcases',
        name: 'TestcaseManage',
        component: () => import('@/pages/test/TestcaseManage.vue'),
        meta: { title: '用例管理', icon: 'FileTextOutlined' }
      },
      {
        path: 'agent/chat',
        name: 'AgentChat',
        component: () => import('@/pages/agent/Chat.vue'),
        meta: { title: 'Agent 对话', icon: 'MessageOutlined' }
      },
      {
        path: 'agent/manage',
        name: 'AgentManage',
        component: () => import('@/pages/agent/AgentManage.vue'),
        meta: { title: '我的 Agent', icon: 'AppstoreOutlined' }
      },
      {
        path: 'agent/llms',
        name: 'LlmManage',
        component: () => import('@/pages/agent/LlmManage.vue'),
        meta: { title: 'LLM 配置', icon: 'ApiOutlined' }
      },
      {
        path: 'agent/token-stats',
        name: 'AgentTokenStats',
        component: () => import('@/pages/agent/TokenStats.vue'),
        meta: { title: 'Token 统计' }
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/pages/Profile.vue'),
        meta: { title: '个人中心', icon: 'UserOutlined' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to) => {
  const token = localStorage.getItem('access_token')
  const authStore = useAuthStore()
  if (to.meta.requiresAuth !== false && !token) {
    return '/login'
  }
  if (to.path === '/login' && token) {
    return '/'
  }
  // 有 token 但用户信息（菜单/按钮权限）未加载时，先加载完成再进入页面，
  // 避免 v-permission 在权限就绪前挂载导致按钮被误移除
  if (token && !authStore.userLoaded) {
    await authStore.fetchUserInfo()
  }
  return true
})

export default router
