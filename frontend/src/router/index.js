import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/pages/Login.vue'),
    meta: { title: '登录', requiresAuth: false }
  },
  {
    path: '/bigscreen',
    name: 'BigScreen',
    component: () => import('@/pages/BigScreen.vue'),
    meta: { title: '数据大屏', requiresAuth: true }
  },
  {
    path: '/smartpark',
    name: 'SmartPark',
    component: () => import('@/pages/SmartPark.vue'),
    meta: { title: '智慧园区', requiresAuth: true }
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
        path: 'device/cameras',
        name: 'CameraManage',
        component: () => import('@/pages/CameraManage.vue'),
        meta: { title: '摄像头管理', icon: 'VideoCameraOutlined' }
      },
      {
        path: 'device/cameras/live/:id',
        name: 'CameraLive',
        component: () => import('@/pages/CameraLive.vue'),
        meta: { title: '摄像头监控', icon: 'VideoCameraOutlined' }
      },
      {
        path: 'device/yolo',
        name: 'YoloModelManage',
        component: () => import('@/pages/YoloModelManage.vue'),
        meta: { title: 'YOLO识别', icon: 'ScanOutlined' }
      },
      {
        path: 'device/yolo/tasks',
        name: 'DetectionTaskManage',
        component: () => import('@/pages/DetectionTaskManage.vue'),
        meta: { title: '识别任务', icon: 'AimOutlined' }
      },
      {
        path: 'device/yolo/results/:taskId',
        name: 'DetectionResultView',
        component: () => import('@/pages/DetectionResultView.vue'),
        meta: { title: '识别结果', icon: 'EyeOutlined' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('access_token')
  if (to.meta.requiresAuth !== false && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/')
  } else {
    next()
  }
})

export default router
