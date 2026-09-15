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

// 上传自动化代码压缩包并触发初始化（异步任务，返回后需轮询项目状态）
// 注意：大包上传必须关闭超时，否则会被 axios 全局 15s 超时中断而误报网络错误
export function uploadProjectCode(projectId, file) {
  const form = new FormData()
  form.append('file', file)
  return request.post(`/projects/${projectId}/code`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 0
  })
}

// 仅重跑依赖安装（初始化失败且代码已落盘时使用，无需重新上传代码包）
export function reinstallProjectCodeDeps(projectId) {
  return request.post(`/projects/${projectId}/code/install`)
}
