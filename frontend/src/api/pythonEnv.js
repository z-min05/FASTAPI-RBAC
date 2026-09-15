import request from './index'

// ==================== Python 环境管理（Miniconda） ====================

// 下拉选项（仅登录，供项目管理选择解释器，返回 status=ready）
export function getPythonEnvOptions() {
  return request.get('/python-envs/options')
}

// 可选的 Python 版本列表（后端配置文件静态列表）
export function getPythonVersions() {
  return request.get('/python-envs/versions')
}

export function getPythonEnvs(params) {
  return request.get('/python-envs', { params })
}

export function getPythonEnv(id) {
  return request.get(`/python-envs/${id}`)
}

export function createPythonEnv(data) {
  return request.post('/python-envs', data)
}

export function updatePythonEnv(id, data) {
  return request.put(`/python-envs/${id}`, data)
}

export function deletePythonEnv(id) {
  return request.delete(`/python-envs/${id}`)
}

export function syncPythonEnv(id) {
  return request.post(`/python-envs/${id}/sync`)
}

export function syncAllPythonEnvs() {
  return request.post('/python-envs/sync-all')
}
