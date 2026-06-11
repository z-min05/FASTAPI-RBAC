import request from './index'

export function getPermissions(params) {
  return request.get('/permissions', { params })
}

export function getPermission(id) {
  return request.get(`/permissions/${id}`)
}

export function createPermission(data) {
  return request.post('/permissions', data)
}

export function updatePermission(id, data) {
  return request.put(`/permissions/${id}`, data)
}

export function deletePermission(id) {
  return request.delete(`/permissions/${id}`)
}
