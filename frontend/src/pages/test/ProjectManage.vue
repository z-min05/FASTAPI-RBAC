<template>
  <div>
    <div class="page-header">
      <a-space>
        <a-input-search
          v-model:value="searchText"
          placeholder="搜索编码/名称"
          style="width: 240px"
          @search="loadData"
          allow-clear
        />
        <a-select
          v-model:value="statusFilter"
          placeholder="状态"
          style="width: 120px"
          allow-clear
          :options="statusOptions"
          @change="loadData"
        />
        <a-button @click="handleReset">重置</a-button>
        <a-button type="primary" @click="showModal()" v-permission="'project:create'">
          <PlusOutlined /> 新增项目
        </a-button>
      </a-space>
    </div>

    <a-table
      :columns="columns"
      :data-source="tableData"
      :loading="loading"
      :pagination="pagination"
      :row-selection="{ selectedRowKeys, onChange: onSelectChange }"
      @change="handleTableChange"
      row-key="id"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'is_active'">
          <a-tag :color="record.is_active ? 'green' : 'red'">
            {{ record.is_active ? '启用' : '停用' }}
          </a-tag>
        </template>
        <template v-if="column.key === 'owner'">
          {{ ownerName(record.owner_id) }}
        </template>
        <template v-if="column.key === 'created_at'">
          {{ formatDate(record.created_at) }}
        </template>
        <template v-if="column.key === 'code_init_status'">
          <a-tooltip placement="topRight" :overlay-style="{ maxWidth: '760px' }">
            <template #title>
              <div class="init-log">{{ initTooltip(record) }}</div>
            </template>
            <a-tag :color="initMeta(record.code_init_status).color">
              {{ initMeta(record.code_init_status).text }}
            </a-tag>
          </a-tooltip>
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="showModal(record)" v-permission="'project:update'">编辑</a-button>
            <a-button
              type="link"
              size="small"
              v-permission="'project:init'"
              :disabled="isInitActive(record)"
              @click="showReinit(record)"
            >{{ record.auto_root_path ? '重新初始化' : '初始化代码' }}</a-button>
            <a-button
              v-if="record.code_init_status === 'failed'"
              type="link"
              size="small"
              v-permission="'project:init'"
              @click="handleReinstall(record)"
            >重装依赖</a-button>
            <a-popconfirm title="确定删除该项目？" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger v-permission="'project:delete'">删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="modalVisible"
      :title="isEdit ? '编辑项目' : '新增项目'"
      @ok="handleSubmit"
      :confirm-loading="submitLoading"
      width="560px"
    >
      <a-form :model="formState" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }">
        <a-form-item label="项目编码" required>
          <a-input v-model:value="formState.code" placeholder="请输入项目编码（唯一）" />
        </a-form-item>
        <a-form-item label="项目名称" required>
          <a-input v-model:value="formState.name" placeholder="请输入项目名称" />
        </a-form-item>
        <a-form-item label="项目描述">
          <a-textarea v-model:value="formState.description" :rows="3" placeholder="请输入项目描述" />
        </a-form-item>
        <a-form-item label="负责人">
          <a-select
            v-model:value="formState.owner_id"
            placeholder="请选择负责人"
            allow-clear
            style="width: 100%"
            :options="ownerOptions"
          />
        </a-form-item>
        <a-form-item label="状态">
          <a-switch v-model:checked="formState.is_active" checked-children="启用" un-checked-children="停用" />
        </a-form-item>
        <a-form-item label="自动化根路径">
          <a-input
            :value="currentAutoRoot"
            disabled
            placeholder="上传代码包后自动生成"
          />
          <div class="form-hint">
            由服务端配置的全局根目录 + 压缩包顶层文件夹名自动推导（…/&lt;项目文件夹&gt;/tests），无需手工填写
          </div>
        </a-form-item>
        <a-form-item label="Python 路径">
          <a-auto-complete
            v-model:value="formState.python_path"
            :options="pythonPathOptions"
            :filter-option="filterPythonPath"
            placeholder="从「Python 环境管理」中选择，或直接输入解释器路径"
            allow-clear
            style="width: 100%"
          />
          <div class="form-hint">下拉选项来自「Python 环境管理」中状态为“可用”的环境，也可手工输入其他路径</div>
        </a-form-item>
        <a-form-item label="自动化代码包">
          <a-upload-dragger
            :show-upload-list="false"
            accept=".zip"
            :before-upload="beforeUploadCode"
          >
            <p class="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p class="ant-upload-text">点击或拖拽 .zip 压缩包到此处</p>
            <p class="ant-upload-hint">
              压缩包顶层需有唯一的项目文件夹（如 meterbot）且内含 tests 目录；
              将整体解压到服务端配置的全局根目录，随后用所选 Python 自动安装 requirements.txt
            </p>
          </a-upload-dragger>
          <div class="form-hint selected-file" v-if="selectedCodeFile">
            <span>已选择：{{ selectedCodeFile.name }}（{{ formatSize(selectedCodeFile.size) }}）</span>
            <a @click="clearCodeFile">移除</a>
          </div>
          <div class="form-hint" v-else-if="isEdit">
            重新选择文件即会重新初始化该项目（同名文件覆盖、多出的旧文件保留）
          </div>
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="reinitVisible"
      title="上传自动化代码包"
      @ok="handleReinit"
      :confirm-loading="reinitLoading"
      ok-text="上传并初始化"
      width="560px"
    >
      <a-alert
        v-if="reinitRecord"
        type="info"
        show-icon
        style="margin-bottom: 12px"
        :message="`项目：${reinitRecord.name}`"
        :description="reinitRecord.auto_root_path
          ? `当前自动化根路径：${reinitRecord.auto_root_path}`
          : '该项目尚未生成自动化根路径'"
      />
      <a-upload-dragger
        :show-upload-list="false"
        accept=".zip"
        :before-upload="beforeUploadReinit"
      >
        <p class="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p class="ant-upload-text">点击或拖拽 .zip 压缩包到此处</p>
        <p class="ant-upload-hint">
          顶层需有唯一的项目文件夹且内含 tests 目录；同名文件覆盖、多出的旧文件保留
        </p>
      </a-upload-dragger>
      <div class="form-hint selected-file" v-if="reinitFile">
        <span>已选择：{{ reinitFile.name }}（{{ formatSize(reinitFile.size) }}）</span>
        <a @click="clearReinitFile">移除</a>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined, InboxOutlined } from '@ant-design/icons-vue'
import {
  getProjects,
  createProject,
  updateProject,
  deleteProject,
  getOwnerOptions,
  uploadProjectCode,
  reinstallProjectCodeDeps
} from '@/api/project'
import { getPythonEnvOptions } from '@/api/pythonEnv'
import dayjs from 'dayjs'

const loading = ref(false)
const submitLoading = ref(false)
const modalVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const searchText = ref('')
const statusFilter = ref(null)
// 创建时间排序：默认倒序（最新创建在前）
const order = ref('desc')
const statusOptions = [
  { label: '启用', value: true },
  { label: '停用', value: false }
]

const columns = computed(() => [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '编码', dataIndex: 'code', key: 'code', width: 120 },
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '负责人', dataIndex: 'owner_id', key: 'owner', width: 120 },
  { title: '状态', dataIndex: 'is_active', key: 'is_active', width: 80 },
  { title: '代码初始化', dataIndex: 'code_init_status', key: 'code_init_status', width: 110 },
  {
    title: '创建时间',
    dataIndex: 'created_at',
    key: 'created_at',
    width: 180,
    sorter: true,
    sortDirections: ['descend', 'ascend'],
    sortOrder: order.value === 'asc' ? 'ascend' : 'descend'
  },
  { title: '自动化根路径', dataIndex: 'auto_root_path', key: 'auto_root_path', ellipsis: true, width: 200 },
  { title: 'Python 路径', dataIndex: 'python_path', key: 'python_path', ellipsis: true, width: 200 },
  { title: '操作', key: 'action', width: 240, fixed: 'right' }
])

const tableData = ref([])
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: (total) => `共 ${total} 条`,
  showSizeChanger: true
})

const selectedRowKeys = ref([])

// 负责人下拉选项（[{ id, username, nickname }]）
const ownerOptions = ref([])

function ownerName(ownerId) {
  if (!ownerId) return '-'
  const o = ownerOptions.value.find(x => x.value === ownerId)
  return o ? o.label : `#${ownerId}`
}

async function loadOwnerOptions() {
  try {
    const res = await getOwnerOptions()
    ownerOptions.value = (res.data || []).map(u => ({
      value: u.id,
      label: u.nickname ? `${u.nickname}(${u.username})` : u.username
    }))
  } catch (e) {
    // 负责人选项加载失败不阻塞页面
  }
}

// Python 解释器下拉选项：来自「Python 环境管理」中 status=ready 的环境
// value 用 python_path（即落库到 projects.python_path 的值），label 用环境名+版本便于识别
const pythonPathOptions = ref([])

async function loadPythonPathOptions() {
  try {
    const res = await getPythonEnvOptions()
    pythonPathOptions.value = (res.data || []).map(env => ({
      value: env.python_path,
      label: `${env.name}（Python ${env.python_version}）`
    }))
  } catch (e) {
    // 环境选项加载失败不阻塞页面（未启用该模块时返回空列表）
  }
}

function filterPythonPath(input, option) {
  const s = (input || '').toLowerCase()
  return String(option.label || '').toLowerCase().includes(s) ||
    String(option.value || '').toLowerCase().includes(s)
}

const formState = reactive({
  code: '',
  name: '',
  description: '',
  owner_id: null,
  is_active: true,
  python_path: ''
})

// ---------- 自动化代码初始化 ----------
// 进行中的状态：此期间禁止再次上传，前端轮询刷新
const ACTIVE_INIT_STATUSES = ['pending', 'extracting', 'installing']

const INIT_STATUS_META = {
  none: { text: '未初始化', color: 'default' },
  pending: { text: '排队中', color: 'blue' },
  extracting: { text: '解压中', color: 'processing' },
  installing: { text: '装依赖中', color: 'processing' },
  ready: { text: '已完成', color: 'green' },
  failed: { text: '失败', color: 'red' }
}

function initMeta(status) {
  return INIT_STATUS_META[status] || { text: status || '-', color: 'default' }
}

function isInitActive(record) {
  return ACTIVE_INIT_STATUSES.includes(record.code_init_status)
}

function initTooltip(record) {
  const parts = []
  if (record.code_init_error) parts.push(`失败原因：${record.code_init_error}`)
  if (record.code_init_at) parts.push(`完成时间：${formatDate(record.code_init_at)}`)
  if (record.code_init_log) {
    const log = record.code_init_log
    parts.push(log.length > 2000 ? `…\n${log.slice(-2000)}` : log)
  }
  return parts.join('\n') || '尚未执行代码初始化'
}

// 当前编辑项目的自动化根路径（只读展示，由初始化任务写入）
const currentAutoRoot = ref('')

// 新增/编辑弹窗中选择的 zip（不自动上传，提交时统一上传）
// 用 show-upload-list=false + 自管状态，避免 beforeUpload 返回 false 时列表项行为不确定
const selectedCodeFile = ref(null)

function formatSize(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

function isZipFile(file) {
  if (!file.name.toLowerCase().endsWith('.zip')) {
    message.error('请上传 .zip 格式的压缩包')
    return false
  }
  return true
}

// 返回 false 阻止 antdv 自动上传，交由提交时统一处理
function beforeUploadCode(file) {
  if (!isZipFile(file)) return false
  selectedCodeFile.value = file
  return false
}

function clearCodeFile() {
  selectedCodeFile.value = null
}

// 重新初始化弹窗
const reinitVisible = ref(false)
const reinitRecord = ref(null)
const reinitLoading = ref(false)
const reinitFile = ref(null)

function showReinit(record) {
  reinitRecord.value = record
  reinitFile.value = null
  reinitVisible.value = true
}

function beforeUploadReinit(file) {
  if (!isZipFile(file)) return false
  reinitFile.value = file
  return false
}

function clearReinitFile() {
  reinitFile.value = null
}

async function handleReinit() {
  if (!reinitFile.value) {
    message.warning('请先选择 .zip 压缩包')
    return
  }
  reinitLoading.value = true
  try {
    await uploadProjectCode(reinitRecord.value.id, reinitFile.value)
    message.success('代码初始化任务已提交，请稍后刷新查看结果')
    reinitVisible.value = false
    loadData()
  } finally {
    reinitLoading.value = false
  }
}

async function handleReinstall(record) {
  await reinstallProjectCodeDeps(record.id)
  message.success('依赖重装任务已提交，请稍后刷新查看结果')
  loadData()
}

// 列表中存在进行中的任务时，每 5s 轮询一次（页面隐藏时暂停）
let pollTimer = null

function startPoll() {
  stopPoll()
  pollTimer = setInterval(() => {
    if (document.hidden) return
    if (tableData.value.some(isInitActive)) loadData()
  }, 5000)
}

function stopPoll() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function formatDate(val) {
  return val ? dayjs(val).format('YYYY-MM-DD HH:mm:ss') : '-'
}

function onSelectChange(keys) {
  selectedRowKeys.value = keys
}

async function loadData() {
  loading.value = true
  try {
    const params = { page: pagination.current, page_size: pagination.pageSize, order: order.value }
    if (searchText.value) params.keyword = searchText.value
    if (statusFilter.value !== null && statusFilter.value !== undefined) params.is_active = statusFilter.value
    const res = await getProjects(params)
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } finally {
    loading.value = false
  }
}

function handleReset() {
  searchText.value = ''
  statusFilter.value = null
  pagination.current = 1
  loadData()
}

function handleTableChange(pag, _filters, sorter) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  // 排序切换时回到第一页；取消排序（第三下）回到默认倒序
  const next = sorter && sorter.order ? (sorter.order === 'ascend' ? 'asc' : 'desc') : 'desc'
  if (next !== order.value) pagination.current = 1
  order.value = next
  loadData()
}

function showModal(record) {
  isEdit.value = !!record
  // 每次打开都清空已选文件，避免上次残留导致误重新初始化
  selectedCodeFile.value = null
  if (record) {
    editId.value = record.id
    currentAutoRoot.value = record.auto_root_path || ''
    Object.assign(formState, {
      code: record.code,
      name: record.name,
      description: record.description || '',
      owner_id: record.owner_id,
      is_active: record.is_active,
      python_path: record.python_path || ''
    })
  } else {
    editId.value = null
    currentAutoRoot.value = ''
    Object.assign(formState, {
      code: '',
      name: '',
      description: '',
      owner_id: null,
      is_active: true,
      python_path: ''
    })
  }
  modalVisible.value = true
}

async function handleSubmit() {
  if (!formState.code || !formState.name) {
    message.warning('请填写项目编码和名称')
    return
  }
  submitLoading.value = true
  try {
    // auto_root_path 由服务端初始化任务推导写入，不提交
    const payload = {
      code: formState.code,
      name: formState.name,
      description: formState.description,
      owner_id: formState.owner_id,
      is_active: formState.is_active,
      python_path: formState.python_path
    }
    let projectId = editId.value
    if (isEdit.value) {
      await updateProject(projectId, payload)
      message.success('更新成功')
    } else {
      const res = await createProject(payload)
      projectId = res.data.id
      message.success('创建成功')
    }

    // 选了压缩包则接着触发代码初始化；上传失败不回滚项目，避免用户重复建项目
    if (selectedCodeFile.value) {
      try {
        await uploadProjectCode(projectId, selectedCodeFile.value)
        message.success('代码初始化任务已提交，请稍后刷新查看结果')
      } catch (e) {
        message.warning(`项目已保存，但代码初始化提交失败：${e?.message || '请重新上传'}`)
      }
    }

    modalVisible.value = false
    loadData()
  } finally {
    submitLoading.value = false
  }
}

async function handleDelete(id) {
  await deleteProject(id)
  message.success('删除成功')
  loadData()
}

onMounted(() => {
  loadData()
  loadOwnerOptions()
  loadPythonPathOptions()
  startPoll()
})

onBeforeUnmount(stopPoll)
</script>

<style scoped>
.page-header {
  margin-bottom: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.form-hint {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}
.form-hint.selected-file {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #1677ff;
}
/* 初始化日志浮层：内容过长时内部滚动，避免浮层超出屏幕 */
.init-log {
  max-height: 60vh;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.6;
}
</style>
