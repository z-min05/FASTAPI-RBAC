import request from './index'

// ==================== 企业微信群机器人 ====================

// 计划绑定下拉选项（仅 id/name/enabled，无需 wecom-robot 权限）
export function getRobotOptions() {
  return request.get('/wecom-robots/options')
}

export function getWecomRobots(params) {
  return request.get('/wecom-robots', { params })
}

export function createWecomRobot(data) {
  return request.post('/wecom-robots', data)
}

export function updateWecomRobot(id, data) {
  return request.put(`/wecom-robots/${id}`, data)
}

export function deleteWecomRobot(id) {
  return request.delete(`/wecom-robots/${id}`)
}

export function testWecomRobot(id) {
  return request.post(`/wecom-robots/${id}/test`)
}
