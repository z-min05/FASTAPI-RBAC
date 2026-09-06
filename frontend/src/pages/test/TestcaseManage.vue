<template>
  <div>
    <div class="page-header">
      <a-space wrap>
        <a-select
          v-model:value="filters.project_id"
          placeholder="项目"
          style="width: 160px"
          allow-clear
          :options="projectOptions"
          @change="onProjectChange"
        />
        <a-select
          v-model:value="filters.module"
          placeholder="模块"
          style="width: 140px"
          allow-clear
          :options="moduleOptions"
          @change="onFilterChange"
        />
        <a-select
          v-model:value="filters.priority"
          placeholder="优先级"
          style="width: 110px"
          allow-clear
          :options="priorityOptions"
          @change="onFilterChange"
        />
        <a-select
          v-model:value="filters.status"
          placeholder="状态"
          style="width: 120px"
          allow-clear
          :options="statusOptions"
          @change="onFilterChange"
        />
        <a-input-search
          v-model:value="filters.keyword"
          placeholder="标题/模块关键字"
          style="width: 200px"
          @search="handleSearch"
          @change="onKeywordChange"
          allow-clear
        />
        <a-button @click="handleReset">重置</a-button>
        <a-button type="primary" @click="showForm()" v-permission="'testcase:create'">
          <PlusOutlined /> 新增用例
        </a-button>
        <a-button danger :disabled="!selectedRowKeys.length" @click="handleBatchDelete" v-permission="'testcase:delete'">
          批量删除
        </a-button>
        <a-button @click="handleImport" v-permission="'testcase:import'">导入</a-button>
        <a-button @click="handleExport" v-permission="'testcase:export'">导出</a-button>
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
        <template v-if="column.key === 'project'">
          <span>{{ record.project_name || record.project_code || '-' }}</span>
        </template>
        <template v-if="column.key === 'priority'">
          <a-tag :color="priorityColor(record.priority)">{{ record.priority }}</a-tag>
        </template>
        <template v-if="column.key === 'status'">
          <a-tag :color="statusColor(record.status)">{{ statusText(record.status) }}</a-tag>
        </template>
        <template v-if="column.key === 'case_type'">
          {{ caseTypeText(record.case_type) }}
        </template>
        <template v-if="column.key === 'created_at'">
          {{ formatDate(record.created_at) }}
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="showDetail(record)">详情</a-button>
            <a-button type="link" size="small" @click="showForm(record)" v-permission="'testcase:update'">编辑</a-button>
            <a-popconfirm title="确定删除该用例？" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger v-permission="'testcase:delete'">删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 详情 -->
    <a-modal v-model:open="detailVisible" title="用例详情" :footer="null" width="720px">
      <a-descriptions bordered :column="2" size="small">
        <a-descriptions-item label="标题" :span="2">{{ detail.title }}</a-descriptions-item>
        <a-descriptions-item label="项目">{{ detail.project_name || '-' }}</a-descriptions-item>
        <a-descriptions-item label="模块">{{ detail.module }}</a-descriptions-item>
        <a-descriptions-item label="优先级"><a-tag :color="priorityColor(detail.priority)">{{ detail.priority }}</a-tag></a-descriptions-item>
        <a-descriptions-item label="状态"><a-tag :color="statusColor(detail.status)">{{ statusText(detail.status) }}</a-tag></a-descriptions-item>
        <a-descriptions-item label="类型">{{ caseTypeText(detail.case_type) }}</a-descriptions-item>
        <a-descriptions-item label="来源">{{ detail.source || '-' }}</a-descriptions-item>
        <a-descriptions-item label="标签">{{ detail.tags || '-' }}</a-descriptions-item>
        <a-descriptions-item label="前置条件" :span="2"><span style="white-space: pre-wrap">{{ detail.precondition || '-' }}</span></a-descriptions-item>
        <a-descriptions-item label="测试步骤" :span="2"><span style="white-space: pre-wrap">{{ detail.steps || '-' }}</span></a-descriptions-item>
        <a-descriptions-item label="预期结果" :span="2"><span style="white-space: pre-wrap">{{ detail.expected_result }}</span></a-descriptions-item>
        <a-descriptions-item label="模块编码">{{ detail.module_code || '-' }}</a-descriptions-item>
        <a-descriptions-item label="用例编码">{{ detail.case_code || '-' }}</a-descriptions-item>
      </a-descriptions>
    </a-modal>

    <!-- 导入弹窗 -->
    <a-modal
      v-model:open="importVisible"
      title="导入用例"
      ok-text="确认导入"
      cancel-text="取消"
      :confirm-loading="importLoading"
      @ok="handleImportSubmit"
      width="560px"
    >
      <a-alert
        type="info"
        show-icon
        message="请先下载模板，按模板格式填写后选择 CSV 文件，点击「确认导入」提交"
        style="margin-bottom: 16px"
      />
      <a-upload
        :before-upload="handleFileSelect"
        :show-upload-list="false"
        accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      >
        <a-button :icon="h(UploadOutlined)">选择 CSV / Excel 文件</a-button>
      </a-upload>
      <div v-if="selectedFile" style="margin-top: 12px; color: rgba(0, 0, 0, 0.65)">
        已选择：{{ selectedFile.name }}（{{ (selectedFile.size / 1024).toFixed(1) }} KB）
      </div>
      <a-divider style="margin: 16px 0 8px" />
      <a-button type="link" :icon="h(DownloadOutlined)" @click="handleDownloadTemplate">
        下载导入模板
      </a-button>
    </a-modal>

    <!-- 新增/编辑 -->
    <a-drawer
      v-model:open="formVisible"
      :title="isEdit ? '编辑用例' : '新增用例'"
      :width="640"
      :footer-style="{ textAlign: 'right' }"
    >
      <a-form :model="formState" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }">
        <a-form-item label="所属项目" required>
          <a-select
            v-model:value="formState.project_id"
            placeholder="请选择项目"
            :options="projectOptions"
            show-search
            option-filter-prop="label"
          />
        </a-form-item>
        <a-form-item label="标题" required>
          <a-input v-model:value="formState.title" placeholder="请输入用例标题" />
        </a-form-item>
        <a-form-item label="模块" required>
          <a-input v-model:value="formState.module" placeholder="请输入模块，如 auth / order" />
        </a-form-item>
        <a-form-item label="优先级">
          <a-select v-model:value="formState.priority" :options="priorityOptions" />
        </a-form-item>
        <a-form-item label="类型">
          <a-select v-model:value="formState.case_type" :options="caseTypeOptions" />
        </a-form-item>
        <a-form-item label="来源">
          <a-input v-model:value="formState.source" placeholder="需求文档 / 接口文档 / 经验总结" />
        </a-form-item>
        <a-form-item label="前置条件">
          <a-textarea v-model:value="formState.precondition" :rows="2" placeholder="前置条件" />
        </a-form-item>
        <a-form-item label="测试步骤">
          <a-textarea v-model:value="formState.steps" :rows="4" placeholder="每行一条步骤，如：1. 调用 /auth/login" />
        </a-form-item>
        <a-form-item label="预期结果" required>
          <a-textarea v-model:value="formState.expected_result" :rows="3" placeholder="预期结果" />
        </a-form-item>
        <a-form-item label="状态">
          <a-select v-model:value="formState.status" :options="statusOptions" />
        </a-form-item>
        <a-form-item label="标签">
          <a-input v-model:value="formState.tags" placeholder="逗号分隔的覆盖点关键词" />
        </a-form-item>
        <a-divider>自动化生成（可选）</a-divider>
        <a-form-item label="模块编码">
          <a-input v-model:value="formState.module_code" placeholder="pytest 文件名，如 test_device_comm_log（需以 test_ 开头）" />
        </a-form-item>
        <a-form-item label="用例编码">
          <a-input v-model:value="formState.case_code" placeholder="pytest 函数名，如 test_list_columns（需以 test_ 开头）" />
        </a-form-item>
      </a-form>
      <div class="drawer-footer">
        <a-space>
          <a-button @click="formVisible = false">取消</a-button>
          <a-button type="primary" :loading="submitLoading" @click="handleSubmit">保存</a-button>
        </a-space>
      </div>
    </a-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, h, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined, UploadOutlined, DownloadOutlined } from '@ant-design/icons-vue'
import {
  getTestcases, getTestcaseModules, getTestcase,
  createTestcase, updateTestcase, deleteTestcase,
  batchDeleteTestcases, exportTestcases, importTestcases, getImportTemplate
} from '@/api/testcase'
import { getAllProjects } from '@/api/project'
import dayjs from 'dayjs'

const loading = ref(false)
const submitLoading = ref(false)
const formVisible = ref(false)
const detailVisible = ref(false)
const importVisible = ref(false)
const importLoading = ref(false)
const selectedFile = ref(null)
const isEdit = ref(false)
const editId = ref(null)
const detail = ref({})

const projectOptions = ref([])
const moduleOptions = ref([])

const priorityOptions = [
  { label: 'P0', value: 'P0' },
  { label: 'P1', value: 'P1' },
  { label: 'P2', value: 'P2' },
  { label: 'P3', value: 'P3' }
]
const statusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '已评审', value: 'reviewed' },
  { label: '已归档', value: 'archived' }
]
const caseTypeOptions = [
  { label: '功能', value: 'function' },
  { label: '接口', value: 'interface' },
  { label: '性能', value: 'performance' },
  { label: '兼容性', value: 'compatibility' },
  { label: '安全', value: 'security' }
]

const filters = reactive({
  project_id: null,
  module: null,
  priority: null,
  status: null,
  source: null,
  keyword: ''
})

// 创建时间排序：默认倒序（最新创建在前）
const order = ref('desc')

const columns = computed(() => [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '标题', dataIndex: 'title', key: 'title', ellipsis: true },
  { title: '项目', key: 'project', width: 120 },
  { title: '模块', dataIndex: 'module', key: 'module', width: 110 },
  { title: '优先级', dataIndex: 'priority', key: 'priority', width: 80 },
  { title: '类型', dataIndex: 'case_type', key: 'case_type', width: 80 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 80 },
  { title: '来源', dataIndex: 'source', key: 'source', width: 100, ellipsis: true },
  {
    title: '创建时间',
    dataIndex: 'created_at',
    key: 'created_at',
    width: 170,
    sorter: true,
    sortDirections: ['descend', 'ascend'],
    sortOrder: order.value === 'asc' ? 'ascend' : 'descend'
  },
  { title: '操作', key: 'action', width: 160, fixed: 'right' }
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

const formState = reactive({
  project_id: null,
  title: '',
  module: '',
  priority: 'P1',
  case_type: 'function',
  source: '',
  precondition: '',
  steps: '',
  expected_result: '',
  status: 'draft',
  tags: '',
  module_code: '',
  case_code: ''
})

function priorityColor(p) {
  return { P0: 'red', P1: 'orange', P2: 'blue', P3: 'default' }[p] || 'default'
}

function statusColor(s) {
  return { draft: 'default', reviewed: 'blue', archived: 'purple' }[s] || 'default'
}

function statusText(s) {
  return { draft: '草稿', reviewed: '已评审', archived: '已归档' }[s] || s
}

function caseTypeText(t) {
  return caseTypeOptions.find(o => o.value === t)?.label || t
}

function formatDate(val) {
  return val ? dayjs(val).format('YYYY-MM-DD HH:mm:ss') : '-'
}

function onSelectChange(keys) {
  selectedRowKeys.value = keys
}

function buildQueryParams() {
  const params = { page: pagination.current, page_size: pagination.pageSize, order: order.value }
  if (filters.project_id) params.project_id = filters.project_id
  if (filters.module) params.module = filters.module
  if (filters.priority) params.priority = filters.priority
  if (filters.status) params.status = filters.status
  if (filters.source) params.source = filters.source
  if (filters.keyword) params.keyword = filters.keyword
  return params
}

async function loadData() {
  loading.value = true
  try {
    const res = await getTestcases(buildQueryParams())
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } finally {
    loading.value = false
  }
}

async function loadProjects() {
  try {
    const res = await getAllProjects()
    projectOptions.value = (res.data || []).map(p => ({ label: p.name, value: p.id }))
    // 有项目时默认选中第一个项目进行筛选；没有任何项目时才不选择
    if (!filters.project_id && projectOptions.value.length) {
      filters.project_id = projectOptions.value[0].value
      filters.module = null
    }
  } catch (e) {
    projectOptions.value = []
  }
  loadModules()
  loadData()
}

async function loadModules() {
  try {
    const params = filters.project_id ? { project_id: filters.project_id } : {}
    const res = await getTestcaseModules(params)
    moduleOptions.value = (res.data || []).map(m => ({ label: m, value: m }))
  } catch (e) {
    moduleOptions.value = []
  }
}

function onProjectChange() {
  // 切换/清空项目：重置模块并立即按当前筛选刷新
  filters.module = null
  pagination.current = 1
  loadModules()
  loadData()
}

// 下拉框（模块/优先级/状态）选中即筛选；点 x 清空即移除该筛选，均立即刷新
function onFilterChange() {
  pagination.current = 1
  loadData()
}

// 关键字搜索框：仅清空（点击 x）时立即生效，输入内容需按回车/点查询触发
function onKeywordChange(e) {
  const value = e && e.target ? e.target.value : e
  if (!value) {
    pagination.current = 1
    loadData()
  }
}

function handleSearch() {
  pagination.current = 1
  loadData()
}

function handleReset() {
  Object.assign(filters, { project_id: null, module: null, priority: null, status: null, source: null, keyword: '' })
  pagination.current = 1
  loadModules()
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

function showForm(record) {
  isEdit.value = !!record
  if (record) {
    editId.value = record.id
    Object.assign(formState, {
      project_id: record.project_id,
      title: record.title,
      module: record.module,
      priority: record.priority,
      case_type: record.case_type,
      source: record.source || '',
      precondition: record.precondition || '',
      steps: record.steps || '',
      expected_result: record.expected_result,
      status: record.status,
      tags: record.tags || '',
      module_code: record.module_code || '',
      case_code: record.case_code || ''
    })
  } else {
    editId.value = null
    Object.assign(formState, {
      project_id: filters.project_id || null,
      title: '',
      module: filters.module || '',
      priority: 'P1',
      case_type: 'function',
      source: '',
      precondition: '',
      steps: '',
      expected_result: '',
      status: 'draft',
      tags: '',
      module_code: '',
      case_code: ''
    })
  }
  formVisible.value = true
}

async function showDetail(record) {
  try {
    const res = await getTestcase(record.id)
    detail.value = res.data || record
  } catch (e) {
    detail.value = record
  }
  detailVisible.value = true
}

async function handleSubmit() {
  if (!formState.project_id) {
    message.warning('请选择所属项目')
    return
  }
  if (!formState.title || !formState.module || !formState.expected_result) {
    message.warning('请填写标题、模块和预期结果')
    return
  }
  submitLoading.value = true
  try {
    if (isEdit.value) {
      await updateTestcase(editId.value, { ...formState })
      message.success('更新成功')
    } else {
      await createTestcase({ ...formState })
      message.success('创建成功')
    }
    formVisible.value = false
    loadData()
    loadModules()
  } finally {
    submitLoading.value = false
  }
}

async function handleDelete(id) {
  await deleteTestcase(id)
  message.success('删除成功')
  loadData()
}

async function handleBatchDelete() {
  await batchDeleteTestcases(selectedRowKeys.value)
  message.success('批量删除成功')
  selectedRowKeys.value = []
  loadData()
}

function handleImport() {
  selectedFile.value = null
  importVisible.value = true
}

function handleFileSelect(file) {
  const isXlsx = /\.xlsx$/i.test(file.name)
  const isCsv = /\.csv$/i.test(file.name)
  if (!isXlsx && !isCsv) {
    message.warning('请选择 CSV 或 xlsx 文件')
    return false
  }
  selectedFile.value = file
  return false // 阻止自动上传
}

// 读取文件：csv 转 utf-8 文本；xlsx 转 base64
function readFileContent(file) {
  return new Promise((resolve, reject) => {
    const isXlsx = /\.xlsx$/i.test(file.name)
    const reader = new FileReader()
    reader.onload = () => {
      if (isXlsx) {
        const base64 = String(reader.result || '').split(',')[1] || ''
        resolve({ content: base64, format: 'xlsx' })
      } else {
        resolve({ content: String(reader.result || ''), format: 'csv' })
      }
    }
    reader.onerror = reject
    if (isXlsx) {
      reader.readAsDataURL(file)
    } else {
      reader.readAsText(file, 'utf-8')
    }
  })
}

async function handleImportSubmit() {
  if (!selectedFile.value) {
    message.warning('请先选择 CSV / Excel 文件')
    return
  }
  importLoading.value = true
  try {
    const { content, format } = await readFileContent(selectedFile.value)
    const res = await importTestcases(content, format)
    const data = res.data || {}
    if (data.failures && data.failures.length) {
      message.warning(`导入完成：成功 ${data.success} 条，失败 ${data.failures.length} 条（第 ${data.failures[0].line} 行: ${data.failures[0].errors.join(';')}）`)
    } else {
      message.success(`导入成功 ${data.success} 条`)
    }
    importVisible.value = false
    selectedFile.value = null
    loadData()
    loadModules()
  } catch (err) {
    // 错误已由拦截器提示
  } finally {
    importLoading.value = false
  }
}

async function handleDownloadTemplate() {
  try {
    const res = await getImportTemplate()
    const data = res.data || {}
    // xlsx 为 base64，解码为二进制后下载
    const binary = atob(data.content || '')
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
    const blob = new Blob([bytes], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = data.filename || 'testcase_import_template.xlsx'
    link.click()
    URL.revokeObjectURL(link.href)
  } catch (err) {
    // 错误已由拦截器提示
  }
}

async function handleExport() {
  const res = await exportTestcases({ ...filters })
  const data = res.data || {}
  const blob = new Blob([data.content || ''], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = data.filename || 'testcases.csv'
  link.click()
  URL.revokeObjectURL(link.href)
}

onMounted(() => {
  // 进入页面时默认选中第一个项目（若有）并按项目加载模块与列表
  loadProjects()
})
</script>

<style scoped>
.page-header {
  margin-bottom: 16px;
}
.drawer-footer {
  margin-top: 16px;
  text-align: right;
}
</style>
