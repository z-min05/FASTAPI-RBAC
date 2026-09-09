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

// ==================== 用例执行日志（历史） ====================

export function getCaseExecutionLogs(planId, ptcId) {
  return request.get(`/plans/${planId}/testcases/${ptcId}/execution-logs`)
}

export function deleteCaseExecutionLog(planId, ptcId, logId) {
  return request.delete(`/plans/${planId}/testcases/${ptcId}/execution-logs/${logId}`)
}

// ==================== 定时执行 ====================

export function getPlanSchedules(planId) {
  return request.get(`/plans/${planId}/schedules`)
}

export function createPlanSchedule(planId, data) {
  return request.post(`/plans/${planId}/schedules`, data)
}

export function updatePlanSchedule(planId, scheduleId, data) {
  return request.put(`/plans/${planId}/schedules/${scheduleId}`, data)
}

export function togglePlanSchedule(planId, scheduleId) {
  return request.patch(`/plans/${planId}/schedules/${scheduleId}/toggle`)
}

export function deletePlanSchedule(planId, scheduleId) {
  return request.delete(`/plans/${planId}/schedules/${scheduleId}`)
}

export function runPlanScheduleNow(planId, scheduleId) {
  return request.post(`/plans/${planId}/schedules/${scheduleId}/run-now`)
}
