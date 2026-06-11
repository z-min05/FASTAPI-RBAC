import request from './index'

export function getMenus(params) {
  return request.get('/menus', { params })
}

export function getMenuTree() {
  return request.get('/menus/tree')
}

export function getMenu(id) {
  return request.get(`/menus/${id}`)
}

export function createMenu(data) {
  return request.post('/menus', data)
}

export function updateMenu(id, data) {
  return request.put(`/menus/${id}`, data)
}

export function deleteMenu(id) {
  return request.delete(`/menus/${id}`)
}
