import request from './index'

// ==================== 工具管理 ====================

export function getTools(params) {
  return request.get('/tools', { params })
}

export function getTool(id) {
  return request.get(`/tools/${id}`)
}

// 上传工具（压缩包 + README，multipart/form-data）
// 大包上传关闭超时，否则会被 axios 全局 15s 超时中断而误报网络错误
export function createTool({ name, description, packageFile, readmeFile }) {
  const form = new FormData()
  form.append('name', name)
  if (description) form.append('description', description)
  form.append('package', packageFile)
  form.append('readme', readmeFile)
  return request.post('/tools', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 0
  })
}

// 下载工具压缩包（文件流）
export function downloadToolPackage(id) {
  return request.get(`/tools/${id}/download`, {
    responseType: 'blob',
    timeout: 0
  })
}

export function deleteTool(id) {
  return request.delete(`/tools/${id}`)
}
