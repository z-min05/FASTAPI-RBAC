import request from './index'

export function getTestcases(params) {
  return request.get('/testcases', { params })
}

export function getTestcaseModules(params) {
  return request.get('/testcases/modules', { params })
}

export function getTestcase(id) {
  return request.get(`/testcases/${id}`)
}

export function createTestcase(data) {
  return request.post('/testcases', data)
}

export function updateTestcase(id, data) {
  return request.put(`/testcases/${id}`, data)
}

export function deleteTestcase(id) {
  return request.delete(`/testcases/${id}`)
}

export function batchDeleteTestcases(ids) {
  return request.post('/testcases/batch-delete', { ids })
}

export function exportTestcases(params) {
  return request.post('/testcases/export', null, { params })
}

export function getImportTemplate() {
  return request.get('/testcases/import-template')
}

export function importTestcases(content, format = 'csv') {
  return request.post('/testcases/import', { content, format })
}
