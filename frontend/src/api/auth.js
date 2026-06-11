import request from './index'

export function login(data) {
  return request.post('/auth/login', data)
}

export function register(data) {
  return request.post('/auth/register', data)
}

export function refreshToken(data) {
  return request.post('/auth/refresh', data)
}

export function getUserMenus() {
  return request.get('/auth/menus')
}
