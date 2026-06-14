import request from './index'

// CRUD
export function getCameras(params) {
  return request.get('/cameras', { params })
}

export function getCamera(id) {
  return request.get(`/cameras/${id}`)
}

export function createCamera(data) {
  return request.post('/cameras', data)
}

export function updateCamera(id, data) {
  return request.put(`/cameras/${id}`, data)
}

export function deleteCamera(id) {
  return request.delete(`/cameras/${id}`)
}

// 连接管理
export function connectCamera(id) {
  return request.post(`/cameras/${id}/connect`)
}

export function disconnectCamera(id) {
  return request.post(`/cameras/${id}/disconnect`)
}

// 云台控制
export function ptzControl(id, data) {
  return request.post(`/cameras/${id}/ptz`, data)
}

export function ptzStop(id) {
  return request.post(`/cameras/${id}/ptz/stop`)
}

export function ptzPreset(id, presetToken) {
  return request.post(`/cameras/${id}/ptz/preset`, { preset_token: presetToken })
}

// 抓图
export function snapshotCamera(id) {
  return request.post(`/cameras/${id}/snapshot`)
}

// 视频流
export function startStream(id) {
  return request.post(`/cameras/${id}/stream/start`)
}

export function stopStream(id) {
  return request.post(`/cameras/${id}/stream/stop`)
}

export function getStreamStatus(id) {
  return request.get(`/cameras/${id}/stream/status`)
}
