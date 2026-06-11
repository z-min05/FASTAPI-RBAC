import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as loginApi, refreshToken as refreshTokenApi, getUserMenus } from '@/api/auth'
import router from '@/router'

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref(localStorage.getItem('access_token') || '')
  const refreshToken = ref(localStorage.getItem('refresh_token') || '')
  const isLoggedIn = ref(!!accessToken.value)
  const menus = ref([])

  async function login(username, password, captchaKey, captchaCode) {
    const res = await loginApi({ username, password, captcha_key: captchaKey, captcha_code: captchaCode })
    const data = res.data
    accessToken.value = data.access_token
    refreshToken.value = data.refresh_token
    isLoggedIn.value = true
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    await fetchMenus()
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
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    router.push('/login')
  }

  return { accessToken, refreshToken, isLoggedIn, menus, login, fetchMenus, doRefreshToken, logout }
})
