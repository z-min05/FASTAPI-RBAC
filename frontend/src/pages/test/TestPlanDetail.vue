<template>
  <a-skeleton v-if="pageLoading" active />
  <div v-else-if="plan" class="plan-detail">
    <!-- 头部：计划信息 -->
    <div class="plan-header">
      <div class="header-left">
        <a-button type="text" class="back-btn" @click="$router.push('/test/plans')">
          <ArrowLeftOutlined />
        </a-button>
        <div class="header-title">
          <div class="title-row">
            <span class="plan-name" :title="plan.name">{{ plan.name }}</span>
            <a-tag color="blue">{{ plan.project_name || `#${plan.project_id}` }}</a-tag>
            <a-tag :color="statusColor(plan.status)">{{ statusLabel(plan.status) }}</a-tag>
          </div>
          <div class="plan-count">已加入 {{ plan.case_count }} 条用例</div>
        </div>
      </div>
      <div class="header-actions">
        <a-button @click="openEditModal()" v-permission="'plan:update'">
          <EditOutlined /> 编辑计划
        </a-button>
        <a-button type="primary" @click="openAddModal" v-permission="'plan:case:add'">
          <PlusOutlined /> 添加用例
        </a-button>
      </div>
    </div>

    <!-- 搜索区 -->
    <div class="filter-bar">
      <a-space>
        <a-input-search
          v-model:value="keyword"
          placeholder="搜索用例标题/模块"
          style="width: 220px"
          @search="reload"
          allow-clear
        />
        <a-select
          v-model:value="resultFilter"
          placeholder="测试结果"
          style="width: 120px"
          allow-clear
          :options="resultOptions"
          @change="reload"
        />
        <a-select
          v-model:value="testerFilter"
          placeholder="测试人"
          style="width: 160px"
          allow-clear
          show-search
          option-filter-prop="label"
          :options="testerOptions"
          @change="reload"
        />
        <a-button @click="resetFilter">重置</a-button>
        <a-button
          v-if="selectedRowKeys.length > 0"
          type="primary"
          @click="handleBatchExecute"
          v-permission="'plan:case:execute'"
        >
          批量执行 ({{ selectedRowKeys.length }})
        </a-button>
      </a-space>
    </div>

    <!-- 计划用例表格 -->
    <a-table
      :columns="columns"
      :data-source="tableData"
      :loading="loading"
      :pagination="pagination"
      @change="handleTableChange"
      row-key="id"
      size="middle"
      :row-selection="{
        selectedRowKeys,
        onChange: onSelectChange,
        getCheckboxProps: r => ({ disabled: !(r.module_code && r.case_code) || r.result === 'running' })
      }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'priority'">
          <a-tag :color="priorityColor(record.priority)">{{ record.priority }}</a-tag>
        </template>
        <template v-if="column.key === 'tester'">
          {{ record.tester_name || '-' }}
        </template>
        <template v-if="column.key === 'result'">
          <a-tag :color="resultColor(record.result)">{{ resultLabel(record.result) }}</a-tag>
        </template>
        <template v-if="column.key === 'updated_at'">
          {{ formatDate(record.updated_at) }}
        </template>
        <template v-if="column.key === 'action'">
          <a-space wrap>
            <a-button type="link" size="small" @click="openCaseDetail(record)">查看</a-button>
            <a-button v-if="record.module_code && record.case_code" type="link" size="small" :disabled="record.result === 'running'" @click="handleExecute(record)" v-permission="'plan:case:execute'">执行</a-button>
            <a-button type="link" size="small" @click="openResultModal(record)" v-permission="'plan:case:result'">记录结果</a-button>
            <a-popconfirm title="确定从该计划中移除这条用例？" @confirm="handleRemove(record.id)">
              <a-button type="link" size="small" danger v-permission="'plan:case:remove'">移除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 编辑计划弹窗 -->
    <a-modal
      v-model:open="editModalVisible"
      title="编辑测试计划"
      @ok="handleEditPlan"
      :confirm-loading="editLoading"
      width="520px"
    >
      <a-form :model="editForm" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }">
        <a-form-item label="计划名称" required>
          <a-input v-model:value="editForm.name" />
        </a-form-item>
        <a-form-item label="所属项目">
          <a-input :value="plan.project_name" disabled />
        </a-form-item>
        <a-form-item label="计划状态">
          <a-select v-model:value="editForm.status" :options="statusOptions" style="width: 100%" />
        </a-form-item>
        <a-form-item label="计划描述">
          <a-textarea v-model:value="editForm.description" :rows="3" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 添加用例弹窗 -->
    <a-modal
      v-model:open="addModalVisible"
      title="添加用例（仅展示本计划所属项目下、未加入的用例）"
      :footer="null"
      width="860px"
      destroy-on-close
    >
      <div class="add-toolbar">
        <a-input-search
          v-model:value="candidateKeyword"
          placeholder="搜索候选用例标题/模块"
          style="width: 240px"
          @search="loadCandidates"
          allow-clear
        />
        <span class="selected-tip">已选 {{ candidateSelected.length }} 条</span>
      </div>
      <a-table
        :columns="candidateColumns"
        :data-source="candidateData"
        :loading="candidateLoading"
        :pagination="candidatePagination"
        @change="handleCandidateChange"
        :row-selection="{ selectedRowKeys: candidateSelected, onChange: onCandidateSelect }"
        row-key="id"
        size="small"
        :scroll="{ y: 420 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'priority'">
            <a-tag :color="priorityColor(record.priority)">{{ record.priority }}</a-tag>
          </template>
          <template v-if="column.key === 'status'">
            <a-tag>{{ tcStatusLabel(record.status) }}</a-tag>
          </template>
        </template>
      </a-table>
      <div class="add-footer">
        <a-button @click="addModalVisible = false">取消</a-button>
        <a-button type="primary" :loading="adding" :disabled="!candidateSelected.length" @click="handleAddCases">
          确定添加（{{ candidateSelected.length }}）
        </a-button>
      </div>
    </a-modal>

    <!-- 记录结果弹窗 -->
    <a-modal
      v-model:open="resultModalVisible"
      title="记录测试结果"
      @ok="handleSaveResult"
      :confirm-loading="resultSaving"
      :width="resultModalWidth"
    >
      <a-form :model="resultForm" :label-col="{ span: 2 }" :wrapper-col="{ span: 21 }">
        <a-form-item label="用例标题">
          <span class="case-title">{{ resultForm.title }}</span>
        </a-form-item>
        <a-form-item label="测试人">
          <a-select
            v-model:value="resultForm.tester_id"
            placeholder="请选择测试人"
            style="width: 100%"
            show-search
            option-filter-prop="label"
            :options="testerOptions"
          />
        </a-form-item>
        <a-form-item label="测试结果" required>
          <a-radio-group v-model:value="resultForm.result" button-style="solid">
            <a-radio-button v-for="r in resultOptions" :key="r.value" :value="r.value">
              {{ r.label }}
            </a-radio-button>
          </a-radio-group>
        </a-form-item>
        <a-form-item label="结果描述">
          <a-textarea
            v-model:value="resultForm.result_desc"
            :rows="18"
            placeholder="自动化执行会自动填充日志；人工记录时请填写失败原因及测试过程"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 用例详情弹窗 -->
    <a-modal
      v-model:open="caseDetailVisible"
      :title="caseDetail.title || '用例详情'"
      :footer="null"
      width="680px"
    >
      <a-descriptions :column="2" size="small" bordered>
        <a-descriptions-item label="模块">{{ caseDetail.module || '-' }}</a-descriptions-item>
        <a-descriptions-item label="优先级">
          <a-tag :color="priorityColor(caseDetail.priority)">{{ caseDetail.priority }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="类型">{{ caseTypeLabel(caseDetail.case_type) }}</a-descriptions-item>
        <a-descriptions-item label="来源">{{ caseDetail.source || '-' }}</a-descriptions-item>
        <a-descriptions-item label="管理状态">{{ tcStatusLabel(caseDetail.status) }}</a-descriptions-item>
        <a-descriptions-item label="结果">
          <a-tag :color="resultColor(caseDetail.result)">{{ resultLabel(caseDetail.result) }}</a-tag>
        </a-descriptions-item>
      </a-descriptions>
      <div class="case-block">
        <div class="case-block-title">前置条件</div>
        <div class="case-block-content">{{ caseDetail.precondition || '无' }}</div>
      </div>
      <div class="case-block">
        <div class="case-block-title">测试步骤</div>
        <pre class="case-block-content">{{ caseDetail.steps || '无' }}</pre>
      </div>
      <div class="case-block">
        <div class="case-block-title">预期结果</div>
        <pre class="case-block-content">{{ caseDetail.expected_result || '无' }}</pre>
      </div>
    </a-modal>
  </div>
  <a-result v-else-if="pageError" status="warning" title="计划加载失败">
    <template #subTitle>{{ pageError }}</template>
    <template #extra>
      <a-button type="primary" @click="$router.push('/test/plans')">返回测试计划列表</a-button>
    </template>
  </a-result>
  <a-empty v-else description="计划不存在或已删除" />
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlusOutlined, ArrowLeftOutlined, EditOutlined } from '@ant-design/icons-vue'
import {
  getPlan,
  updatePlan,
  getTesterOptions,
  getPlanTestcases,
  getPlanCandidates,
  addPlanTestcases,
  updatePlanTestcaseResult,
  removePlanTestcase,
  executePlanTestcase,
  batchExecutePlanTestcases
} from '@/api/plan'
import { useAuthStore } from '@/stores/auth'
import dayjs from 'dayjs'

const route = useRoute()
const authStore = useAuthStore()
const planId = Number(route.params.id)

const plan = ref(null)
const pageLoading = ref(true)
const pageError = ref('')
const loading = ref(false)

// 行选择（批量执行）
const selectedRowKeys = ref([])
function onSelectChange(keys) {
  selectedRowKeys.value = keys
}

// 结果弹窗宽度响应式
const resultModalWidth = ref(800)
function updateResultModalWidth() {
  resultModalWidth.value = Math.min(window.innerWidth * 0.8, 1200)
}
updateResultModalWidth()

// ---------- 常量与文案 ----------
const statusOptions = [
  { label: '未开始', value: 'not_started' },
  { label: '进行中', value: 'in_progress' },
  { label: '已完成', value: 'completed' }
]
const resultOptions = [
  { label: '通过', value: 'pass' },
  { label: '失败', value: 'fail' },
  { label: '阻塞', value: 'blocked' },
  { label: '跳过', value: 'skipped' },
  { label: '执行中', value: 'running' }
]

function statusLabel(status) {
  return { not_started: '未开始', in_progress: '进行中', completed: '已完成' }[status] || status || '-'
}
function statusColor(status) {
  return { not_started: 'default', in_progress: 'processing', completed: 'success' }[status] || 'default'
}
function priorityColor(p) {
  return { P0: 'red', P1: 'orange', P2: 'blue', P3: 'default' }[p] || 'default'
}
function resultLabel(result) {
  if (!result) return '未执行'
  return { pass: '通过', fail: '失败', blocked: '阻塞', skipped: '跳过', running: '执行中' }[result] || result
}
function resultColor(result) {
  if (!result) return 'default'
  return { pass: 'success', fail: 'error', blocked: 'warning', skipped: 'default', running: 'processing' }[result] || 'default'
}
function tcStatusLabel(status) {
  return { draft: '草稿', reviewed: '已评审', archived: '已归档' }[status] || status || '-'
}
function caseTypeLabel(type) {
  const map = {
    function: '功能', interface: '接口', performance: '性能',
    compatibility: '兼容', security: '安全'
  }
  return map[type] || type || '-'
}
function formatDate(val) {
  return val ? dayjs(val).format('YYYY-MM-DD HH:mm:ss') : '-'
}

// ---------- 计划头部 ----------
async function loadPlan() {
  pageLoading.value = true
  pageError.value = ''
  try {
    const res = await getPlan(planId)
    plan.value = res.data
  } catch (e) {
    pageError.value = e?.message || '加载计划失败，请稍后重试'
  } finally {
    pageLoading.value = false
  }
}

function openEditModal() {
  if (!plan.value) return
  Object.assign(editForm, {
    name: plan.value.name,
    status: plan.value.status,
    description: plan.value.description || ''
  })
  editModalVisible.value = true
}

const editModalVisible = ref(false)
const editLoading = ref(false)
const editForm = reactive({ name: '', status: 'not_started', description: '' })

async function handleEditPlan() {
  if (!editForm.name) {
    message.warning('计划名称不能为空')
    return
  }
  editLoading.value = true
  try {
    await updatePlan(planId, {
      name: editForm.name,
      status: editForm.status,
      description: editForm.description
    })
    message.success('更新成功')
    editModalVisible.value = false
    loadPlan()
  } finally {
    editLoading.value = false
  }
}

// ---------- 计划用例列表 ----------
const keyword = ref('')
const resultFilter = ref(null)
const testerFilter = ref(null)
const testerOptions = ref([])

const columns = [
  { title: '用例标题', dataIndex: 'title', key: 'title', ellipsis: true },
  { title: '模块', dataIndex: 'module', key: 'module', width: 120, ellipsis: true },
  { title: '优先级', dataIndex: 'priority', key: 'priority', width: 80 },
  { title: '来源', dataIndex: 'source', key: 'source', width: 110, ellipsis: true },
  { title: '测试人', dataIndex: 'tester_name', key: 'tester', width: 120 },
  { title: '结果', dataIndex: 'result', key: 'result', width: 90 },
  { title: '结果描述', dataIndex: 'result_desc', key: 'result_desc', width: 200, ellipsis: true },
  { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 170 },
  { title: '操作', key: 'action', width: 230, fixed: 'right' }
]

const tableData = ref([])
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: (total) => `共 ${total} 条`,
  showSizeChanger: true
})

async function loadTestcases() {
  loading.value = true
  try {
    const params = { page: pagination.current, page_size: pagination.pageSize }
    if (keyword.value) params.keyword = keyword.value
    if (resultFilter.value) params.result = resultFilter.value
    if (testerFilter.value !== null && testerFilter.value !== undefined) params.tester_id = testerFilter.value
    const res = await getPlanTestcases(planId, params)
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } finally {
    loading.value = false
  }
}

function reload() {
  pagination.current = 1
  loadTestcases()
}

function resetFilter() {
  keyword.value = ''
  resultFilter.value = null
  testerFilter.value = null
  reload()
}

function handleTableChange(pag) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadTestcases()
}

async function loadTesterOptions() {
  try {
    const res = await getTesterOptions()
    testerOptions.value = (res.data || []).map(u => ({
      value: u.id,
      label: u.nickname ? `${u.nickname}(${u.username})` : u.username
    }))
  } catch (e) {
    // 忽略：无下拉权限时仅影响选择器
  }
}

// ---------- 添加用例 ----------
const addModalVisible = ref(false)
const candidateKeyword = ref('')
const candidateData = ref([])
const candidateLoading = ref(false)
const candidateSelected = ref([])
const adding = ref(false)
const candidatePagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: (total) => `共 ${total} 条`
})

const candidateColumns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '用例标题', dataIndex: 'title', key: 'title', ellipsis: true },
  { title: '模块', dataIndex: 'module', key: 'module', width: 130, ellipsis: true },
  { title: '优先级', dataIndex: 'priority', key: 'priority', width: 80 },
  { title: '类型', dataIndex: 'case_type', key: 'case_type', width: 90 },
  { title: '来源', dataIndex: 'source', key: 'source', width: 110, ellipsis: true },
  { title: '状态', dataIndex: 'status', key: 'status', width: 90 }
]

async function loadCandidates() {
  candidateLoading.value = true
  try {
    const params = { page: candidatePagination.current, page_size: candidatePagination.pageSize }
    if (candidateKeyword.value) params.keyword = candidateKeyword.value
    const res = await getPlanCandidates(planId, params)
    candidateData.value = res.data.items || []
    candidatePagination.total = res.data.total || 0
  } finally {
    candidateLoading.value = false
  }
}

function openAddModal() {
  candidateKeyword.value = ''
  candidateSelected.value = []
  candidatePagination.current = 1
  addModalVisible.value = true
  loadCandidates()
}

function onCandidateSelect(keys) {
  candidateSelected.value = keys
}

function handleCandidateChange(pag) {
  candidatePagination.current = pag.current
  candidatePagination.pageSize = pag.pageSize
  loadCandidates()
}

async function handleAddCases() {
  if (!candidateSelected.value.length) {
    message.warning('请先勾选要添加的用例')
    return
  }
  adding.value = true
  try {
    const res = await addPlanTestcases(planId, candidateSelected.value)
    message.success(`已添加 ${res.data.added} 条用例${res.data.skipped ? `，跳过 ${res.data.skipped} 条已在计划中的` : ''}`)
    addModalVisible.value = false
    loadPlan()
    reload()
  } finally {
    adding.value = false
  }
}

// ---------- 记录结果 ----------
const resultModalVisible = ref(false)
const resultSaving = ref(false)
const resultForm = reactive({ ptc_id: null, title: '', tester_id: null, result: null, result_desc: '' })

function openResultModal(record) {
  Object.assign(resultForm, {
    ptc_id: record.id,
    title: record.title,
    tester_id: record.tester_id ?? authStore.userInfo?.id ?? null,
    result: record.result || null,
    result_desc: record.result_desc || ''
  })
  resultModalVisible.value = true
}

async function handleSaveResult() {
  if (!resultForm.result) {
    message.warning('请选择测试结果')
    return
  }
  resultSaving.value = true
  try {
    await updatePlanTestcaseResult(planId, resultForm.ptc_id, {
      tester_id: resultForm.tester_id,
      result: resultForm.result,
      result_desc: resultForm.result_desc
    })
    message.success('结果已保存')
    resultModalVisible.value = false
    loadPlan()
    loadTestcases()
  } finally {
    resultSaving.value = false
  }
}

// ---------- 移除 / 执行 / 查看 ----------
async function handleRemove(ptcId) {
  await removePlanTestcase(planId, ptcId)
  message.success('已从计划中移除')
  loadPlan()
  loadTestcases()
}

async function handleExecute(record) {
  try {
    await executePlanTestcase(planId, record.id)
    message.success('已提交自动化执行，请稍后刷新查看结果')
    loadTestcases()
  } catch (e) {
    // 错误已由拦截器提示
  }
}

async function handleBatchExecute() {
  const ids = selectedRowKeys.value
  if (!ids.length) return
  try {
    await batchExecutePlanTestcases(planId, ids)
    message.success(`已提交批量执行 (${ids.length} 条用例)，串行执行中，请稍后刷新查看结果`)
    selectedRowKeys.value = []
    loadTestcases()
  } catch (e) {
    // 错误已由拦截器提示
  }
}

const caseDetailVisible = ref(false)
const caseDetail = reactive({
  title: '', module: '', priority: '', case_type: '', source: '', status: '',
  precondition: '', steps: '', expected_result: '', result: null
})

function openCaseDetail(record) {
  Object.assign(caseDetail, {
    title: record.title,
    module: record.module,
    priority: record.priority,
    case_type: record.case_type,
    source: record.source,
    status: record.status,
    precondition: record.precondition,
    steps: record.steps,
    expected_result: record.expected_result,
    result: record.result
  })
  caseDetailVisible.value = true
}

onMounted(async () => {
  loadPlan()
  loadTesterOptions()
  loadTestcases()
})
</script>

<style scoped>
.plan-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
  padding: 16px 20px;
  background: #fff;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  margin-bottom: 16px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}
.back-btn {
  flex-shrink: 0;
}
.header-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-left: 4px;
  min-width: 0;
}
.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.plan-name {
  font-size: 18px;
  font-weight: 600;
  max-width: 420px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.plan-count {
  color: #999;
  font-size: 13px;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
  margin-left: auto;
}
.filter-bar {
  margin-bottom: 16px;
}
.add-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.selected-tip {
  color: #666;
}
.add-footer {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
}
.case-title {
  font-weight: 500;
}
.case-block {
  margin-top: 12px;
}
.case-block-title {
  font-weight: 600;
  margin-bottom: 4px;
}
.case-block-content {
  background: #fafafa;
  border: 1px solid #f0f0f0;
  border-radius: 4px;
  padding: 8px 12px;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
}
</style>
