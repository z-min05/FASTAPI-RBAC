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
            <a-tag v-if="plan.agent_name" color="purple">AI 汇总：{{ plan.agent_name }}</a-tag>
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
        <a-button @click="openScheduleDrawer" v-permission="'plan:schedule:list'">
          <FieldTimeOutlined /> 定时执行
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
        <a-button
          v-if="hasRunningCases"
          danger
          @click="handleStopExecution"
          v-permission="'plan:case:execute'"
        >
          停止执行
        </a-button>
        <a-button @click="handleExport">
          <template #icon><DownloadOutlined /></template>
          导出
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
          <a-space>
            <a-button type="link" size="small" @click="openCaseDetail(record)">查看</a-button>
            <a-button v-if="record.module_code && record.case_code" type="link" size="small" :disabled="record.result === 'running'" @click="handleExecute(record)" v-permission="'plan:case:execute'">执行</a-button>
            <a-button type="link" size="small" @click="openLogDrawer(record)" v-permission="'plan:case:list'">日志</a-button>
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
      width="600px"
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
        <a-divider style="margin: 8px 0">结果推送（企业微信群机器人）</a-divider>
        <a-form-item label="推送机器人">
          <a-select
            v-model:value="editForm.robot_ids"
            mode="multiple"
            :options="robotSelectOptions"
            placeholder="批量/定时执行完成后推送统计到群，不选则不推送"
            style="width: 100%"
            allow-clear
            :max-tag-count="4"
          >
            <template #option="{ value, label }">
              <span :class="{ 'opt-disabled': isDisabledRobot(value) }">{{ label }}</span>
            </template>
          </a-select>
          <div class="form-tip">仅在「批量执行」或「定时执行」整轮结束后推送一次统计（含失败明细）</div>
        </a-form-item>
        <a-form-item v-if="agentOptionsLoaded" label="AI 结果汇总">
          <a-select
            v-model:value="editForm.agent_id"
            :options="agentSelectOptions"
            placeholder="选一个当前用户的 Agent，整轮执行完成后由 AI 汇总结果再推送"
            style="width: 100%"
            allow-clear
          />
          <div class="form-tip">保存时会自动为该 Agent 创建会话；AI 返回异常时自动回退为统计推送</div>
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

    <!-- 历史执行日志抽屉 -->
    <a-drawer
      v-model:open="logDrawerVisible"
      :title="logDrawerTitle"
      width="820px"
      destroy-on-close
    >
      <div class="log-toolbar">
        <a-space>
          <a-button size="small" :loading="logLoading" @click="loadLogs">
            <template #icon><ReloadOutlined /></template>
            刷新
          </a-button>
          <span v-if="logs.length" class="log-tip">
            共 {{ logs.length }} 次执行记录；最新一次不允许删除
          </span>
        </a-space>
      </div>
      <a-empty v-if="!logLoading && !logs.length" description="暂无执行日志（自动化执行或手动记录结果后自动产生）" />
      <div v-for="log in logs" :key="log.id" class="log-item">
        <div class="log-head">
          <a-tag :color="resultColor(log.result)">{{ resultLabel(log.result) }}</a-tag>
          <span class="log-time">{{ logTimeRange(log) }}</span>
          <span class="log-tester">测试人：{{ log.tester_name || '-' }}</span>
          <div class="log-head-right">
            <a-popconfirm
              v-if="!log.is_latest"
              title="确定删除这条历史执行日志？"
              @confirm="handleDeleteLog(log)"
              v-permission="'plan:case:execute'"
            >
              <a-tooltip :title="log.is_latest ? '最新一次执行日志不允许删除' : ''">
                <a-button
                  type="link"
                  size="small"
                  danger
                  :disabled="deletingLogId === log.id"
                >删除</a-button>
              </a-tooltip>
            </a-popconfirm>
            <a-tag v-else color="blue" style="cursor: not-allowed">最新一次不可删除</a-tag>
            <a-button type="link" size="small" @click="toggleLog(log.id)">
              {{ expandedLogId === log.id ? '收起日志' : '展开日志' }}
            </a-button>
          </div>
        </div>
        <pre v-if="expandedLogId === log.id" class="log-content">{{ log.log_content || '（无日志内容）' }}</pre>
      </div>
    </a-drawer>

    <!-- 定时执行任务抽屉 -->
    <a-drawer
      v-model:open="scheduleDrawerVisible"
      title="定时执行任务"
      width="920px"
      destroy-on-close
    >
      <div class="schedule-toolbar">
        <a-space>
          <a-button size="small" :loading="schedulesLoading" @click="loadSchedules">
            <template #icon><ReloadOutlined /></template>
            刷新
          </a-button>
          <span class="schedule-tip">
            任务到点后自动串行执行该计划下的自动化用例，同一时间仅允许一轮执行
          </span>
        </a-space>
        <a-button
          type="primary"
          size="small"
          @click="openScheduleModal()"
          v-permission="'plan:schedule:create'"
        >
          <template #icon><PlusOutlined /></template>
          新建定时执行
        </a-button>
      </div>
      <a-table
        :columns="scheduleColumns"
        :data-source="schedules"
        :loading="schedulesLoading"
        :pagination="false"
        row-key="id"
        size="middle"
        :scroll="{ x: 1000 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'name'">
            <span :title="record.description || record.name">{{ record.name }}</span>
          </template>
          <template v-else-if="column.key === 'cron'">
            <code class="cron-text">{{ record.cron_expr }}</code>
          </template>
          <template v-else-if="column.key === 'mode'">
            <a-tag v-if="record.mode === 'full'" color="blue">全量</a-tag>
            <a-tag v-else color="orange">指定 {{ record.case_ids ? record.case_ids.length : 0 }} 条</a-tag>
          </template>
          <template v-else-if="column.key === 'next'">
            <span v-if="!record.enabled" class="muted">已停用</span>
            <span v-else-if="record.is_running">执行中</span>
            <span v-else>{{ record.next_run_at ? formatDate(record.next_run_at) : '-' }}</span>
          </template>
          <template v-else-if="column.key === 'last'">
            <template v-if="record.is_running">
              <a-tag color="processing">执行中</a-tag>
            </template>
            <template v-else>
              <a-tag v-if="record.last_status" :color="scheduleStatusColor(record.last_status)">
                {{ scheduleStatusLabel(record.last_status) }}
              </a-tag>
              <span v-if="record.last_skip_reason" class="skip-reason" :title="record.last_skip_reason">
                {{ record.last_skip_reason }}
              </span>
              <div class="schedule-last-time">
                {{ record.last_run_at ? formatDate(record.last_run_at) : '尚未运行' }}
              </div>
            </template>
          </template>
          <template v-else-if="column.key === 'enabled'">
            <a-switch
              size="small"
              :checked="record.enabled"
              :loading="togglingId === record.id"
              @change="handleToggleSchedule(record)"
              v-permission="'plan:schedule:update'"
            />
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space :wrap="false">
              <a-button
                type="link"
                size="small"
                :loading="runningNowId === record.id"
                :disabled="record.is_running"
                @click="handleRunNow(record)"
                v-permission="'plan:case:execute'"
              >立即执行</a-button>
              <a-button
                type="link"
                size="small"
                @click="openScheduleModal(record)"
                v-permission="'plan:schedule:update'"
              >编辑</a-button>
              <a-popconfirm title="确定删除该定时执行任务？" @confirm="handleDeleteSchedule(record)">
                <a-button type="link" size="small" danger v-permission="'plan:schedule:delete'">删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-drawer>

    <!-- 新建/编辑定时执行弹窗 -->
    <a-modal
      v-model:open="scheduleModalVisible"
      :title="scheduleForm.id ? '编辑定时执行任务' : '新建定时执行任务'"
      @ok="handleSaveSchedule"
      :confirm-loading="scheduleSaving"
      width="640px"
    >
      <a-form :model="scheduleForm" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }">
        <a-form-item label="任务名称" required>
          <a-input v-model:value="scheduleForm.name" maxlength="100" placeholder="如：每日凌晨2点回归" />
        </a-form-item>
        <a-form-item label="cron 表达式" required>
          <a-input v-model:value="scheduleForm.cron_expr" placeholder="分 时 日 月 周，如：0 2 * * *" />
          <div class="cron-hint">
            示例：<code>0 2 * * *</code> 每天 02:00；<code>*/10 * * * *</code> 每 10 分钟；
            支持 5 段（分 时 日 月 周）或 6 段（含秒）
          </div>
        </a-form-item>
        <a-form-item label="执行范围" required>
          <a-radio-group v-model:value="scheduleForm.mode" button-style="solid">
            <a-radio-button value="full">全量执行</a-radio-button>
            <a-radio-button value="custom">指定用例</a-radio-button>
          </a-radio-group>
          <div class="cron-hint">
            {{ scheduleForm.mode === 'full'
              ? '执行计划内所有已配置模块编码/用例编码的自动化用例'
              : '仅执行下方勾选的自动化用例（需已配置模块编码/用例编码）' }}
          </div>
        </a-form-item>
        <a-form-item v-if="scheduleForm.mode === 'custom'" label="选择用例" required>
          <a-select
            v-model:value="scheduleForm.case_ids"
            mode="multiple"
            style="width: 100%"
            :options="scheduleCandidateOptions"
            :loading="scheduleCandidatesLoading"
            placeholder="从计划内可自动化的用例中选择"
            option-filter-prop="label"
            :max-tag-count="6"
            allow-clear
          />
          <div class="cron-hint">计划内可自动化用例共 {{ scheduleCandidates.length }} 条</div>
        </a-form-item>
        <a-form-item label="任务说明">
          <a-textarea v-model:value="scheduleForm.description" :rows="2" maxlength="500" placeholder="可选" />
        </a-form-item>
      </a-form>
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
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlusOutlined, ArrowLeftOutlined, EditOutlined, DownloadOutlined, ReloadOutlined, FieldTimeOutlined } from '@ant-design/icons-vue'
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
  batchExecutePlanTestcases,
  stopPlanExecution,
  exportPlanTestcases,
  getCaseExecutionLogs,
  deleteCaseExecutionLog,
  getPlanSchedules,
  createPlanSchedule,
  updatePlanSchedule,
  togglePlanSchedule,
  deletePlanSchedule,
  runPlanScheduleNow
} from '@/api/plan'
import { useAuthStore } from '@/stores/auth'
import { listAgents } from '@/api/agent'
import { getRobotOptions } from '@/api/wecomRobot'
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

// 当前页面是否有执行中的用例（显示停止按钮）
const hasRunningCases = computed(() => {
  return tableData.value ? tableData.value.some(tc => tc.result === 'running') : false
})

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
    description: plan.value.description || '',
    robot_ids: plan.value.robot_ids || [],
    agent_id: plan.value.agent_id ?? null
  })
  editModalVisible.value = true
}

const editModalVisible = ref(false)
const editLoading = ref(false)
const editForm = reactive({ name: '', status: 'not_started', description: '', robot_ids: [], agent_id: null })

// Agent 下拉（当前用户 Agent；Agent 服务未启用时隐藏）
const agentOptions = ref([])
const agentOptionsLoaded = ref(false)
const agentSelectOptions = computed(() =>
  agentOptions.value.map(a => ({ value: a.id, label: a.enabled ? a.name : `${a.name}（已停用）` }))
)

async function loadAgents() {
  try {
    const res = await listAgents({ scope: 'mine', page_size: 50 })
    agentOptions.value = (res.data?.items || []).map(a => ({ id: a.id, name: a.name, enabled: a.enabled }))
    agentOptionsLoaded.value = true
  } catch (e) {
    agentOptionsLoaded.value = false
  }
}

// 机器人下拉（详情编辑始终为编辑态：允许保留已停用的历史绑定）
const robotOptions = ref([]) // [{id,name,enabled}]
const robotSelectOptions = computed(() =>
  robotOptions.value.map(r => ({ value: r.id, label: r.enabled ? r.name : `${r.name}（已停用）`, enabled: r.enabled }))
)

function isDisabledRobot(id) {
  const r = robotOptions.value.find(item => item.id === id)
  return !!r && !r.enabled
}

async function loadRobots() {
  try {
    const res = await getRobotOptions()
    robotOptions.value = res.data || []
  } catch (e) {
    // 下拉加载失败不阻塞
  }
}

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
      description: editForm.description,
      robot_ids: editForm.robot_ids,
      agent_id: editForm.agent_id ?? null
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
  { title: '结果描述', dataIndex: 'result_desc', key: 'result_desc', width: 120, ellipsis: true },
  { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 170 },
  { title: '操作', key: 'action', width: 320, fixed: 'right' }
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

async function handleExport() {
  const blob = await exportPlanTestcases(planId)
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `plan_${planId}_testcases.csv`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  window.URL.revokeObjectURL(url)
  message.success('导出成功')
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
const resultForm = reactive({ ptc_id: null, title: '', result: null, result_desc: '' })

async function openResultModal(record) {
  Object.assign(resultForm, {
    ptc_id: record.id,
    title: record.title,
    result: record.result || null,
    result_desc: record.result_desc || ''
  })
  resultModalVisible.value = true
  // 用最新一次执行日志（完整内容）预填结果描述，避免只显示自动化执行的简化摘要
  try {
    const res = await getCaseExecutionLogs(planId, record.id)
    const latest = (res.data || [])[0]
    if (latest) {
      if (latest.result) resultForm.result = latest.result
      if (latest.log_content) resultForm.result_desc = latest.log_content
    }
  } catch (e) {
    // 拉取失败忽略，保留默认值
  }
}

async function handleSaveResult() {
  if (!resultForm.result) {
    message.warning('请选择测试结果')
    return
  }
  resultSaving.value = true
  try {
    await updatePlanTestcaseResult(planId, resultForm.ptc_id, {
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

async function handleStopExecution() {
  try {
    await stopPlanExecution(planId)
    message.success('已请求停止批量执行，剩余未执行的用例将被跳过')
  } catch (e) {
    // 错误已由拦截器提示
  }
}

// ---------- 定时执行 ----------
const scheduleDrawerVisible = ref(false)
const schedulesLoading = ref(false)
const schedules = ref([])
const togglingId = ref(null)
const runningNowId = ref(null)
const scheduleCandidatesLoading = ref(false)
const scheduleCandidates = ref([])
const scheduleModalVisible = ref(false)
const scheduleSaving = ref(false)
const scheduleForm = reactive({
  id: null,
  name: '',
  cron_expr: '',
  mode: 'full',
  case_ids: [],
  description: ''
})

const scheduleCandidateOptions = computed(() =>
  scheduleCandidates.value.map(t => ({
    value: t.testcase_id,
    label: t.title || `用例#${t.testcase_id}`
  }))
)

const scheduleColumns = [
  { title: '任务名称', dataIndex: 'name', key: 'name', width: 170, ellipsis: true },
  { title: 'cron 表达式', dataIndex: 'cron_expr', key: 'cron', width: 130 },
  { title: '执行范围', key: 'mode', width: 110 },
  { title: '下次执行', key: 'next', width: 165 },
  { title: '最近执行', key: 'last', width: 220 },
  { title: '启用', key: 'enabled', width: 70, align: 'center' },
  { title: '操作', key: 'action', width: 200, fixed: 'right' }
]

function scheduleStatusLabel(status) {
  return { ok: '成功', skipped: '已跳过', error: '失败' }[status] || status || '未运行'
}
function scheduleStatusColor(status) {
  return { ok: 'success', skipped: 'warning', error: 'error' }[status] || 'default'
}

async function loadSchedules() {
  schedulesLoading.value = true
  try {
    const res = await getPlanSchedules(planId)
    schedules.value = res.data || []
  } catch (e) {
    // 错误已由拦截器提示
  } finally {
    schedulesLoading.value = false
  }
}

async function loadScheduleCandidates() {
  scheduleCandidatesLoading.value = true
  const all = []
  try {
    // 复用计划用例接口循环分页拉全量，仅保留已配置模块编码/用例编码（可自动化执行）的用例
    let total = Infinity
    for (let page = 1; page <= 30 && all.length < total; page++) {
      const res = await getPlanTestcases(planId, { page, page_size: 100 })
      const items = res.data.items || []
      total = res.data.total ?? total
      all.push(...items)
      if (items.length < 100) break
    }
    scheduleCandidates.value = all.filter(t => t.module_code && t.case_code)
  } catch (e) {
    scheduleCandidates.value = []
  } finally {
    scheduleCandidatesLoading.value = false
  }
}

async function openScheduleDrawer() {
  scheduleDrawerVisible.value = true
  loadSchedules()
  loadScheduleCandidates()
}

function openScheduleModal(schedule) {
  Object.assign(scheduleForm, {
    id: schedule ? schedule.id : null,
    name: schedule ? schedule.name : '',
    cron_expr: schedule ? schedule.cron_expr : '',
    mode: schedule ? schedule.mode : 'full',
    case_ids: schedule && schedule.case_ids ? [...schedule.case_ids] : [],
    description: schedule ? schedule.description || '' : ''
  })
  scheduleModalVisible.value = true
}

async function handleSaveSchedule() {
  const f = scheduleForm
  if (!f.name || !f.name.trim()) {
    message.warning('请填写任务名称')
    return
  }
  if (!f.cron_expr || !f.cron_expr.trim()) {
    message.warning('请填写 cron 表达式')
    return
  }
  if (f.mode === 'custom' && (!f.case_ids || !f.case_ids.length)) {
    message.warning('指定用例模式至少选择一个用例')
    return
  }
  scheduleSaving.value = true
  try {
    const data = {
      name: f.name.trim(),
      cron_expr: f.cron_expr.trim(),
      mode: f.mode,
      description: f.description || null
    }
    if (f.mode === 'custom') data.case_ids = f.case_ids
    if (f.id) {
      await updatePlanSchedule(planId, f.id, data)
      message.success('更新成功')
    } else {
      await createPlanSchedule(planId, data)
      message.success('创建成功，将按 cron 表达式定时自动执行')
    }
    scheduleModalVisible.value = false
    loadSchedules()
  } catch (e) {
    // 错误已由拦截器提示
  } finally {
    scheduleSaving.value = false
  }
}

async function handleToggleSchedule(record) {
  togglingId.value = record.id
  try {
    const res = await togglePlanSchedule(planId, record.id)
    message.success(res.data.enabled ? '已启用定时执行' : '已停用定时执行')
    // 就地回写行数据（含重算后的下次执行时间）
    Object.assign(record, res.data)
  } catch (e) {
    // 错误已由拦截器提示
  } finally {
    togglingId.value = null
  }
}

async function handleRunNow(record) {
  runningNowId.value = record.id
  try {
    await runPlanScheduleNow(planId, record.id)
    message.success('已触发立即执行，用例将串行执行，请稍后刷新查看结果')
    loadSchedules()
    loadTestcases()
  } catch (e) {
    // 错误已由拦截器提示
  } finally {
    runningNowId.value = null
  }
}

async function handleDeleteSchedule(record) {
  try {
    await deletePlanSchedule(planId, record.id)
    message.success('删除成功')
    loadSchedules()
  } catch (e) {
    // 错误已由拦截器提示
  }
}

// ---------- 历史执行日志 ----------
const logDrawerVisible = ref(false)
const logDrawerTitle = ref('执行日志')
const logRecord = reactive({ ptc_id: null, title: '' })
const logs = ref([])
const logLoading = ref(false)
const deletingLogId = ref(null)
const expandedLogId = ref(null)

function logTimeRange(log) {
  const start = log.started_at ? dayjs(log.started_at).format('MM-DD HH:mm:ss') : ''
  const end = log.finished_at ? dayjs(log.finished_at).format('MM-DD HH:mm:ss') : ''
  if (start && end && start !== end) return `${start} ~ ${end}`
  return start || end || '-'
}

function openLogDrawer(record) {
  logRecord.ptc_id = record.id
  logRecord.title = record.title
  logDrawerTitle.value = `执行日志 · ${record.title || `#${record.id}`}`
  logs.value = []
  expandedLogId.value = null
  logDrawerVisible.value = true
  loadLogs()
}

async function loadLogs() {
  logLoading.value = true
  try {
    const res = await getCaseExecutionLogs(planId, logRecord.ptc_id)
    logs.value = res.data || []
  } finally {
    logLoading.value = false
  }
}

function toggleLog(logId) {
  expandedLogId.value = expandedLogId.value === logId ? null : logId
}

async function handleDeleteLog(log) {
  deletingLogId.value = log.id
  try {
    await deleteCaseExecutionLog(planId, logRecord.ptc_id, log.id)
    message.success('历史执行日志已删除')
    if (expandedLogId.value === log.id) expandedLogId.value = null
    await loadLogs()
    loadTestcases()
  } finally {
    deletingLogId.value = null
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
  loadRobots()
  loadAgents()
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
.robot-line {
  margin-top: 2px;
}
.form-tip {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}
.opt-disabled {
  color: #bbb;
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
.log-toolbar {
  margin-bottom: 12px;
}
.log-tip {
  color: #999;
  font-size: 12px;
}
.log-item {
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  margin-bottom: 12px;
  overflow: hidden;
}
.log-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  padding: 8px 12px;
  background: #fafafa;
}
.log-time {
  color: #666;
  font-size: 12px;
  margin: 0 8px 0 4px;
}
.log-tester {
  color: #999;
  font-size: 12px;
  margin-right: 4px;
}
.log-head-right {
  display: flex;
  align-items: center;
  margin-left: auto;
  flex-shrink: 0;
}
.log-content {
  margin: 0;
  padding: 12px;
  max-height: 60vh;
  overflow: auto;
  font-size: 12px;
  line-height: 1.6;
  background: #1e1e1e;
  color: #d4d4d4;
  white-space: pre-wrap;
  word-break: break-all;
}
.schedule-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.schedule-tip {
  color: #999;
  font-size: 12px;
}
.schedule-last-time {
  color: #999;
  font-size: 12px;
  line-height: 18px;
  margin-top: 2px;
}
.skip-reason {
  color: #d4a017;
  font-size: 12px;
  margin-left: 6px;
  display: inline-block;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: middle;
}
.cron-hint {
  color: #999;
  font-size: 12px;
  margin-top: 4px;
}
.cron-text {
  background: #f5f5f5;
  border: 1px solid #f0f0f0;
  border-radius: 2px;
  padding: 0 4px;
  font-family: 'Consolas', 'Monaco', monospace;
}
.muted {
  color: #bbb;
}
</style>
