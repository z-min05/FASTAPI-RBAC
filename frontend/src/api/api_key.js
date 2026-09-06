import request from './index'

export function getApiKeys(params) {
  return request.get('/api-keys', { params })
}

export function getApiKeyRoles() {
  return request.get('/api-keys/roles')
}

export function createApiKey(data) {
  return request.post('/api-keys', data)
}

export function updateApiKeyStatus(id, is_active) {
  return request.put(`/api-keys/${id}/status`, { is_active })
}

export function deleteApiKey(id) {
  return request.delete(`/api-keys/${id}`)
}

export function regenerateApiKey(id) {
  return request.post(`/api-keys/${id}/regenerate`)
}