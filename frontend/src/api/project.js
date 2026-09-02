import request from './index'

export function getProjects(params) {
  return request.get('/projects', { params })
}

export function getAllProjects() {
  return request.get('/projects/all')
}

export function getOwnerOptions() {
  return request.get('/projects/owners')
}

export function getProject(id) {
  return request.get(`/projects/${id}`)
}

export function createProject(data) {
  return request.post('/projects', data)
}

export function updateProject(id, data) {
  return request.put(`/projects/${id}`, data)
}

export function deleteProject(id) {
  return request.delete(`/projects/${id}`)
}
