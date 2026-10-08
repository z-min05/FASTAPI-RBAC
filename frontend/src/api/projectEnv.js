import request from './index'

// ==================== 自动化测试环境管理 ====================
// 环境快照存于 {项目根}/.envs/<name>.env，生效环境为 {项目根}/.env；
// 「当前生效环境」由内容比对判定。'@active' 表示当前生效的 .env。

export function getProjectEnvs(projectId) {
  return request.get(`/projects/${projectId}/envs`)
}

export function getProjectEnv(projectId, name) {
  return request.get(`/projects/${projectId}/envs/${encodeURIComponent(name)}`)
}

export function getProjectActiveEnv(projectId) {
  return request.get(`/projects/${projectId}/env`)
}

export function createProjectEnv(projectId, data) {
  return request.post(`/projects/${projectId}/envs`, data)
}

// 上传本地文件作为新环境（环境名由文件名推导，前端读成文本后提交）
export function uploadProjectEnv(projectId, data) {
  return request.post(`/projects/${projectId}/envs/upload`, data)
}

export function saveProjectEnv(projectId, name, data) {
  return request.put(`/projects/${projectId}/envs/${encodeURIComponent(name)}`, data)
}

export function saveProjectActiveEnv(projectId, data) {
  return request.put(`/projects/${projectId}/env`, data)
}

export function applyProjectEnv(projectId, name) {
  return request.post(`/projects/${projectId}/envs/${encodeURIComponent(name)}/apply`)
}

export function renameProjectEnv(projectId, name, newName) {
  return request.post(`/projects/${projectId}/envs/${encodeURIComponent(name)}/rename`, {
    new_name: newName
  })
}

export function deleteProjectEnv(projectId, name) {
  return request.delete(`/projects/${projectId}/envs/${encodeURIComponent(name)}`)
}

export function diffProjectEnvs(projectId, left, right) {
  return request.get(`/projects/${projectId}/envs/diff`, { params: { left, right } })
}

export function downloadProjectEnv(projectId, name) {
  return request.get(`/projects/${projectId}/envs/${encodeURIComponent(name)}/download`, {
    responseType: 'blob',
    timeout: 0
  })
}
