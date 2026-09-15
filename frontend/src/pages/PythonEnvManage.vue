<template>
  <div>
    <div class="page-header">
      <a-space>
        <a-input-search
          v-model:value="searchText"
          placeholder="搜索环境名称"
          style="width: 220px"
          @search="handleSearch"
          allow-clear
        />
        <a-select
          v-model:value="statusFilter"
          placeholder="状态"
          style="width: 130px"
          allow-clear
          :options="statusOptions"
          @change="handleSearch"
        />
        <a-button @click="handleReset">重置</a-button>
        <a-button @click="handleRefresh">
          <ReloadOutlined /> 刷新
        </a-button>
        <a-button @click="handleSyncAll" v-permission="'python-env:sync'">
          <SyncOutlined /> 全量校验
        </a-button>
        <a-button type="primary" @click="showCreateModal" v-permission="'python-env:create'">
          <PlusOutlined /> 新增环境
        </a-button>
      </a-space>
      <span class="page-hint">
        conda 操作在后台异步执行，创建/删除中可稍后刷新或等待自动刷新查看结果
      </span>
    </div>

    <a-table
      :columns="columns"
      :data-source="tableData"
      :loading="loading"
      :pagination="pagination"
      @change="handleTableChange"
      row-key="id"
      size="middle"
      :scroll="{ x: 1400 }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'env_path'">
          <a-typography-text code class="path-text">{{ record.env_path }}</a-typography-text>
          <a-button type="link" size="small" @click="copyText(record.env_path)">复制</a-button>
        </template>
        <template v-if="column.key === 'python_path'">
          <a-typography-text code class="path-text">{{ record.python_path }}</a-typography-text>
          <a-button type="link" size="small" @click="copyText(record.python_path)">复制</a-button>
        </template>
        <template v-if="column.key === 'status'">
          <a-tooltip>
            <template #title>
              <div v-if="record.error_msg">{{ record.error_msg }}</div>
              <div v-if="record.last_synced_at">上次校验：{{ formatDate(record.last_synced_at) }}</div>
              <div v-if="!record.error_msg && !record.last_synced_at">{{ statusText(record.status) }}</div>
            </template>
            <a-tag :color="statusColor(record.status)">{{ statusText(record.status) }}</a-tag>
          </a-tooltip>
        </template>
        <template v-if="column.key === 'created_by'">
          {{ record.created_by_name || '-' }}
        </template>
        <template v-if="column.key === 'created_at'">
          {{ formatDate(record.created_at) }}
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button
              type="link"
              size="small"
              :disabled="isActive(record.status)"
              @click="showEditModal(record)"
              v-permission="'python-env:update'"
            >编辑</a-button>
            <a-button
              type="link"
              size="small"
              :disabled="isActive(record.status)"
              @click="handleSync(record)"
              v-permission="'python-env:sync'"
            >校验</a-button>
            <a-popconfirm
              title="确定删除该环境？将删除实际环境目录与数据库记录，请先确保没有项目在使用它。"
              ok-text="确认删除"
              cancel-text="取消"
              :disabled="isActive(record.status)"
              @confirm="handleDelete(record.id)"
            >
              <a-button
                type="link"
                size="small"
                danger
                :disabled="isActive(record.status)"
                v-permission="'python-env:delete'"
              >删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 新增弹窗 -->
    <a-modal
      v-model:open="createVisible"
      title="新增 Python 环境"
      @ok="handleCreate"
      :confirm-loading="submitLoading"
      width="620px"
    >
      <a-alert
        type="info"
        show-icon
        message="保存后将异步执行 conda 创建，可能需要数分钟，请稍后刷新查看结果"
        style="margin-bottom: 16px"
      />
      <a-form :model="createForm" :rules="createRules" ref="createFormRef" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }">
        <a-form-item name="name" label="环境名称" required>
          <a-input v-model:value="createForm.name" placeholder="仅字母/数字/下划线/中划线，如 test_py311" />
          <div class="form-hint">名称同时作为环境目录名，创建后不可修改</div>
        </a-form-item>
        <a-form-item name="python_version" label="Python 版本" required>
          <a-select v-model:value="createForm.python_version" placeholder="请选择 Python 版本" :options="versionOptions" />
          <div class="form-hint">版本列表来自后端配置文件，创建后不可修改</div>
        </a-form-item>
        <a-form-item name="description" label="备注">
          <a-textarea v-model:value="createForm.description" :rows="3" placeholder="用途说明（选填）" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 编辑弹窗（仅备注可改） -->
    <a-modal
      v-model:open="editVisible"
      title="编辑 Python 环境"
      @ok="handleEdit"
      :confirm-loading="submitLoading"
      width="620px"
    >
      <a-form :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }">
        <a-form-item label="环境名称">
          <a-input :value="editRecord?.name" disabled />
        </a-form-item>
        <a-form-item label="Python 版本">
          <a-input :value="editRecord?.python_version" disabled />
        </a-form-item>
        <a-form-item label="环境路径">
          <a-input :value="editRecord?.env_path" disabled />
        </a-form-item>
        <a-form-item label="解释器路径">
          <a-input :value="editRecord?.python_path" disabled />
        </a-form-item>
        <a-form-item label="备注">
          <a-textarea v-model:value="editForm.description" :rows="3" placeholder="用途说明（选填）" />
        </a-form-item>
      </a-form>
      <div class="form-hint">名称与 Python 版本创建后不可修改；如需更换请删除后重建</div>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined, ReloadOutlined, SyncOutlined } from '@ant-design/icons-vue'
import {
  getPythonEnvs,
  getPythonVersions,
  createPythonEnv,
  updatePythonEnv,
  deletePythonEnv,
  syncPythonEnv,
  syncAllPythonEnvs
} from '@/api/pythonEnv'
import dayjs from 'dayjs'

// 状态机展示映射（与后端 python_env_service.py 保持一致）
const STATUS_MAP = {
  pending: { color: 'blue', text: '排队中' },
  creating: { color: 'processing', text: '创建中' },
  ready: { color: 'green', text: '可用' },
  failed: { color: 'red', text: '失败' },
  syncing: { color: 'processing', text: '校验中' },
  lost: { color: 'orange', text: '环境丢失' },
  deleting: { color: 'processing', text: '删除中' }
}
// 进行中状态：存在这些记录时自动轮询刷新
const ACTIVE_STATUSES = ['pending', 'creating', 'syncing', 'deleting']

const loading = ref(false)
const submitLoading = ref(false)
const createVisible = ref(false)
const editVisible = ref(false)
const editRecord = ref(null)
const searchText = ref('')
const statusFilter = ref(null)
const versions = ref([])

const tableData = ref([])
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  pageSizeOptions: ['10', '20', '50', '100']
})

const createFormRef = ref(null)
const createForm = reactive({
  name: '',
  python_version: undefined,
  description: ''
})
const editForm = reactive({
  description: ''
})

const createRules = {
  name: [
    { required: true, message: '请输入环境名称', trigger: 'blur' },
    {
      pattern: /^[A-Za-z0-9_-]{1,50}$/,
      message: '仅允许字母、数字、下划线、中划线，长度 1-50',
      trigger: 'blur'
    }
  ],
  python_version: [{ required: true, message: '请选择 Python 版本', trigger: 'change' }]
}

const columns = [
  { title: '名称', dataIndex: 'name', key: 'name', width: 160, ellipsis: true },
  { title: 'Python 版本', dataIndex: 'python_version', key: 'python_version', width: 110 },
  { title: '环境路径', key: 'env_path', width: 320 },
  { title: '解释器路径', key: 'python_path', width: 320 },
  { title: '状态', key: 'status', width: 110 },
  { title: '创建人', key: 'created_by', width: 110 },
  { title: '创建时间', key: 'created_at', width: 160 },
  { title: '操作', key: 'action', width: 190, fixed: 'right' }
]

const statusOptions = computed(() =>
  Object.entries(STATUS_MAP).map(([value, cfg]) => ({ label: cfg.text, value }))
)
const versionOptions = computed(() => versions.value.map((v) => ({ label: v, value: v })))

function statusColor(status) {
  return STATUS_MAP[status]?.color || 'default'
}
function statusText(status) {
  return STATUS_MAP[status]?.text || status
}
function isActive(status) {
  return ACTIVE_STATUSES.includes(status)
}
function formatDate(val) {
  return val ? dayjs(val).format('YYYY-MM-DD HH:mm') : '-'
}

// ---------- 自动轮询：列表中存在进行中记录时每 5s 刷新一次 ----------
let pollTimer = null

function needsPolling() {
  return tableData.value.some((r) => isActive(r.status))
}
function startPolling() {
  if (pollTimer) return
  pollTimer = setInterval(async () => {
    if (document.hidden) return
    await loadData()
    if (!needsPolling()) stopPolling()
  }, 5000)
}
function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function loadData() {
  loading.value = true
  try {
    const params = { page: pagination.current, page_size: pagination.pageSize }
    if (searchText.value) params.keyword = searchText.value
    if (statusFilter.value) params.status = statusFilter.value
    const res = await getPythonEnvs(params)
    if (res.code === 200 && res.data) {
      tableData.value = res.data.items || []
      pagination.total = res.data.total || 0
    }
  } catch (e) {
    // 错误已由拦截器处理
  } finally {
    loading.value = false
    if (needsPolling()) startPolling()
    else stopPolling()
  }
}

async function loadVersions() {
  try {
    const res = await getPythonVersions()
    if (res.code === 200 && res.data) {
      versions.value = res.data.versions || []
    }
  } catch (e) {
    // 错误已由拦截器处理
  }
}

function handleTableChange(pag) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadData()
}

function handleSearch() {
  pagination.current = 1
  loadData()
}

function handleReset() {
  searchText.value = ''
  statusFilter.value = null
  pagination.current = 1
  loadData()
}

function handleRefresh() {
  loadData()
}

async function copyText(text) {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    message.success('已复制')
  } catch (e) {
    message.warning('复制失败，请手动选中复制')
  }
}

function resetCreateForm() {
  createForm.name = ''
  createForm.python_version = undefined
  createForm.description = ''
  createFormRef.value?.clearValidate()
}

function showCreateModal() {
  resetCreateForm()
  createVisible.value = true
}

function showEditModal(record) {
  editRecord.value = record
  editForm.description = record.description || ''
  editVisible.value = true
}

async function handleCreate() {
  try {
    await createFormRef.value?.validate()
  } catch {
    return
  }
  submitLoading.value = true
  try {
    const res = await createPythonEnv({
      name: createForm.name.trim(),
      python_version: createForm.python_version,
      description: createForm.description || null
    })
    if (res && res.code === 200) {
      message.success('创建任务已提交，请稍后刷新查看结果')
      createVisible.value = false
      pagination.current = 1
      loadData()
    }
  } catch (e) {
    // 错误已由拦截器处理
  } finally {
    submitLoading.value = false
  }
}

async function handleEdit() {
  if (!editRecord.value) return
  submitLoading.value = true
  try {
    const res = await updatePythonEnv(editRecord.value.id, {
      description: editForm.description || null
    })
    if (res && res.code === 200) {
      message.success('保存成功')
      editVisible.value = false
      loadData()
    }
  } catch (e) {
    // 错误已由拦截器处理
  } finally {
    submitLoading.value = false
  }
}

async function handleSync(record) {
  try {
    const res = await syncPythonEnv(record.id)
    if (res && res.code === 200) {
      message.success('同步任务已提交，请稍后刷新查看结果')
      loadData()
    }
  } catch (e) {
    // 错误已由拦截器处理
  }
}

async function handleSyncAll() {
  try {
    const res = await syncAllPythonEnvs()
    if (res && res.code === 200) {
      const count = res.data?.count ?? 0
      message.success(count ? `已提交 ${count} 个环境的校验任务` : '没有需要校验的环境')
      loadData()
    }
  } catch (e) {
    // 错误已由拦截器处理
  }
}

async function handleDelete(id) {
  try {
    const res = await deletePythonEnv(id)
    if (res && res.code === 200) {
      message.success('删除任务已提交，请稍后刷新查看结果')
      loadData()
    }
  } catch (e) {
    // 错误已由拦截器处理
  }
}

function handleVisibilityChange() {
  if (!document.hidden && needsPolling()) {
    loadData()
  }
}

onMounted(() => {
  loadData()
  loadVersions()
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onBeforeUnmount(() => {
  stopPolling()
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})
</script>

<style scoped>
.page-header {
  margin-bottom: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.page-hint {
  font-size: 12px;
  color: #999;
}
.form-hint {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}
.path-text {
  word-break: break-all;
}
</style>
