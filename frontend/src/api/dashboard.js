import request from './index'

export function getDashboardStats() {
  return request.get('/dashboard/stats')
}