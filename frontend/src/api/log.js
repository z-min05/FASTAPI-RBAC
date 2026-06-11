import request from './index'

export function getLogs(params) {
  return request.get('/logs', { params })
}

export function getUserLogs(userId) {
  return request.get(`/logs/user/${userId}`)
}
