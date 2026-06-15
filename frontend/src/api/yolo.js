import request from './index'

// ==================== YOLO模型 ====================
export function getYoloModels(params) {
  return request.get('/yolo/models', { params })
}

export function getYoloModel(id) {
  return request.get(`/yolo/models/${id}`)
}

export function createYoloModel(formData) {
  return request.post('/yolo/models', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export function updateYoloModel(id, formData) {
  return request.put(`/yolo/models/${id}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export function deleteYoloModel(id) {
  return request.delete(`/yolo/models/${id}`)
}

// ==================== 识别任务 ====================
export function getDetectionTasks(params) {
  return request.get('/yolo/tasks', { params })
}

export function getDetectionTask(id) {
  return request.get(`/yolo/tasks/${id}`)
}

export function createDetectionTask(data) {
  return request.post('/yolo/tasks', data)
}

export function updateDetectionTask(id, data) {
  return request.put(`/yolo/tasks/${id}`, data)
}

export function deleteDetectionTask(id) {
  return request.delete(`/yolo/tasks/${id}`)
}

export function toggleDetectionTask(id, active) {
  return request.post(`/yolo/tasks/${id}/toggle`, null, { params: { active } })
}

export function runDetectionOnce(id) {
  return request.post(`/yolo/tasks/${id}/run`)
}

export function getRunningTasks() {
  return request.get('/yolo/tasks/running')
}

// ==================== 识别结果 ====================
export function getDetectionResults(taskId, params) {
  return request.get(`/yolo/results/${taskId}`, { params })
}

export function getDetectionResult(id) {
  return request.get(`/yolo/result/${id}`)
}

export function getResultImageUrl(id) {
  return `/api/v1/yolo/result/${id}/image`
}

export function getResultAnnotatedUrl(id) {
  return `/api/v1/yolo/result/${id}/annotated`
}
