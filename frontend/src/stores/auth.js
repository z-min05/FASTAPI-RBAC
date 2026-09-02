import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as loginApi, refreshToken as refreshTokenApi, getUserMenus, getUserInfo } from '@/api/auth'
import router from '@/router'

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref(localStorage.getItem('access_token') || '')
  const refreshToken = ref(localStorage.getItem('refresh_token') || '')
  const isLoggedIn = ref(!!accessToken.value)
  const menus = ref([])
  const userInfo = ref(null)
  const apiPermissions = ref([])
  const buttonPermissions = ref([])
  // 用户信息（含菜单/按钮权限）是否已加载完成，供路由守卫等待
  const userLoaded = ref(false)

  async function login(username, password, captchaKey, captchaCode) {
    const res = await loginApi({ username, password, captcha_key: captchaKey, captcha_code: captchaCode })
    const data = res.data
    accessToken.value = data.access_token
    refreshToken.value = data.refresh_token
    isLoggedIn.value = true
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    await fetchUserInfo()
    router.push('/')
  }

  async function fetchMenus() {
    try {
      const res = await getUserMenus()
      menus.value = res.data || []
    } catch (e) {
      menus.value = []
    }
  }

  async function fetchUserInfo() {
    try {
      const res = await getUserInfo()
      const data = res.data || {}
      userInfo.value = data.user || null
      menus.value = data.menus || []
      apiPermissions.value = data.api_permissions || []
      buttonPermissions.value = data.button_permissions || []
      userLoaded.value = true
    } catch (e) {
      // 回退到单独获取菜单
      userInfo.value = null
      apiPermissions.value = []
      buttonPermissions.value = []
      userLoaded.value = true
      await fetchMenus()
    }
  }

  async function doRefreshToken() {
    const res = await refreshTokenApi({ refresh_token: refreshToken.value })
    const data = res.data
    accessToken.value = data.access_token
    refreshToken.value = data.refresh_token
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
  }

  function logout() {
    accessToken.value = ''
    refreshToken.value = ''
    isLoggedIn.value = false
    menus.value = []
    userInfo.value = null
    apiPermissions.value = []
    buttonPermissions.value = []
    userLoaded.value = false
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    router.push('/login')
  }

  return {
    accessToken, refreshToken, isLoggedIn, menus,
    userInfo, apiPermissions, buttonPermissions, userLoaded,
    login, fetchMenus, fetchUserInfo, doRefreshToken, logout
  }
})
