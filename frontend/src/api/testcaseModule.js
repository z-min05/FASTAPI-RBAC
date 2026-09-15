import request from './index'

export function getModuleTree(projectId) {
  return request.get('/testcase-modules/tree', { params: { project_id: projectId } })
}

export function getModuleDetail(moduleId) {
  return request.get(`/testcase-modules/${moduleId}`)
}

export function createModule(data) {
  return request.post('/testcase-modules', data)
}

export function updateModule(moduleId, data) {
  return request.put(`/testcase-modules/${moduleId}`, data)
}

export function deleteModule(moduleId) {
  return request.delete(`/testcase-modules/${moduleId}`)
}
