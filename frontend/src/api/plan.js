import request from './index'

// ==================== 测试计划 ====================

export function getPlans(params) {
  return request.get('/plans', { params })
}

export function getPlan(id) {
  return request.get(`/plans/${id}`)
}

export function createPlan(data) {
  return request.post('/plans', data)
}

export function updatePlan(id, data) {
  return request.put(`/plans/${id}`, data)
}

export function deletePlan(id) {
  return request.delete(`/plans/${id}`)
}

export function getTesterOptions() {
  return request.get('/plans/testers')
}

// ==================== 计划用例 ====================

export function getPlanTestcases(planId, params) {
  return request.get(`/plans/${planId}/testcases`, { params })
}

export function getPlanCandidates(planId, params) {
  return request.get(`/plans/${planId}/candidates`, { params })
}

export function addPlanTestcases(planId, testcaseIds) {
  return request.post(`/plans/${planId}/testcases`, { testcase_ids: testcaseIds })
}

export function updatePlanTestcaseResult(planId, ptcId, data) {
  return request.put(`/plans/${planId}/testcases/${ptcId}/result`, data)
}

export function removePlanTestcase(planId, ptcId) {
  return request.delete(`/plans/${planId}/testcases/${ptcId}`)
}

export function executePlanTestcase(planId, ptcId) {
  return request.post(`/plans/${planId}/testcases/${ptcId}/execute`)
}

export function batchExecutePlanTestcases(planId, ptcIds) {
  return request.post(`/plans/${planId}/testcases/batch-execute`, { ptc_ids: ptcIds })
}

export function stopPlanExecution(planId) {
  return request.post(`/plans/${planId}/testcases/stop-execution`)
}

export function exportPlanTestcases(planId) {
  return request.get(`/plans/${planId}/testcases/export`, { responseType: 'blob' })
}
