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
        <a-button
          v-if="canSync"
          v-permission="'testcase:sync'"
          :loading="syncing"
          @click="handleSync"
        >同步用例</a-button>
      </a-space>
    </div>

    <div class="testcase-body">
      <div class="module-panel">
        <TestcaseModuleTree
          :key="treeVersion"
          :project-id="filters.project_id"
          :selected-module-id="filters.module_id"
          @select="onModuleSelect"
          @create-case="onCreateCaseFromTree"
          @changed="onModuleChanged"
        />
      </div>
      <div class="table-panel">
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
      </div>
    </div>

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
            @change="onFormProjectChange"
          />
        </a-form-item>
        <a-form-item label="标题" required>
          <a-input v-model:value="formState.title" placeholder="请输入用例标题" />
        </a-form-item>
        <a-form-item label="模块" required>
          <a-tree-select
            v-model:value="formState.module_id"
            placeholder="请选择末级模块"
            :tree-data="leafModuleOptions"
            tree-node-filter-prop="label"
            show-search
            allow-clear
            style="width: 100%"
          />
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
          <span class="readonly-text">{{ currentModulePath || '-' }}</span>
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
  getTestcases, getTestcase,
  createTestcase, updateTestcase, deleteTestcase,
  batchDeleteTestcases, exportTestcases, importTestcases, getImportTemplate,
  syncTestcases
} from '@/api/testcase'
import { getModuleTree } from '@/api/testcaseModule'
import { getAllProjects } from '@/api/project'
import TestcaseModuleTree from '@/components/TestcaseModuleTree.vue'
import dayjs from 'dayjs'

const loading = ref(false)
const syncing = ref(false)
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
// 当前项目的模块树：供新增/编辑用例弹窗选择末级模块、展示模块路径
const moduleTree = ref([])
// 编辑时记录的模块路径，用于模块树里查不到该节点时的兜底展示
const editModuleCode = ref('')
// 自增后强制重建左侧模块树（同步用例、模块/用例变更后刷新）
const treeVersion = ref(0)

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
  module_id: null,
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
  module_id: null,
  priority: 'P1',
  case_type: 'function',
  source: '',
  precondition: '',
  steps: '',
  expected_result: '',
  status: 'draft',
  tags: '',
  case_code: ''
})

// 末级模块选项：label 用名称链（如 设备管理/通信日志），避免同名模块歧义
const leafModuleOptions = computed(() => {
  const options = []
  const walk = (nodes, prefix) => {
    nodes.forEach((node) => {
      const path = prefix ? `${prefix}/${node.name}` : node.name
      if (node.is_leaf === true) {
        options.push({ label: path, value: node.id })
      } else {
        walk(node.children || [], path)
      }
    })
  }
  walk(moduleTree.value, '')
  return options
})

// 模块编码只读展示：由所选模块带出相对路径，不提交给后端
const currentModulePath = computed(() => {
  const node = findModuleById(moduleTree.value, formState.module_id)
  return (node && node.module_path) || editModuleCode.value || ''
})

function findModuleById(nodes, id) {
  if (!id) return null
  for (const node of nodes) {
    if (node.id === id) return node
    const found = findModuleById(node.children || [], id)
    if (found) return found
  }
  return null
}

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
  // 按模块筛选时包含子模块下的用例（点非末级节点可看到整棵子树）
  if (filters.module_id) {
    params.module_id = filters.module_id
    params.include_children = true
  }
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
    // 保留 auto_root_path，用于判断是否显示「同步用例」按钮
    projectOptions.value = (res.data || []).map(p => ({
      label: p.name, value: p.id, auto_root_path: p.auto_root_path
    }))
    // 有项目时默认选中第一个项目进行筛选；没有任何项目时才不选择
    if (!filters.project_id && projectOptions.value.length) {
      filters.project_id = projectOptions.value[0].value
      filters.module_id = null
    }
  } catch (e) {
    projectOptions.value = []
  }
  loadModuleTree()
  loadData()
}

async function loadModuleTree(projectId) {
  const pid = projectId || filters.project_id
  if (!pid) {
    moduleTree.value = []
    return
  }
  try {
    const res = await getModuleTree(pid)
    moduleTree.value = res.data || []
  } catch (e) {
    moduleTree.value = []
  }
}

// 模块结构或用例数变化后刷新左侧模块树
function refreshModuleTree() {
  treeVersion.value += 1
  loadModuleTree()
}

function onProjectChange() {
  // 切换/清空项目：清空模块筛选并回到第一页，左侧模块树随 projectId 变化自动重载
  filters.module_id = null
  pagination.current = 1
  loadModuleTree()
  loadData()
}

// 点击树节点：按模块筛选列表（含子模块）
function onModuleSelect(moduleId) {
  filters.module_id = moduleId || null
  pagination.current = 1
  loadData()
}

// 树节点的「+用例」快捷入口
function onCreateCaseFromTree(moduleId) {
  showForm(null, moduleId)
}

// 模块增删改成功后：同步表单模块选项并刷新列表
function onModuleChanged() {
  loadModuleTree()
  loadData()
}

// 下拉框（优先级/状态）选中即筛选；点 x 清空即移除该筛选，均立即刷新
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
  Object.assign(filters, { project_id: null, module_id: null, priority: null, status: null, source: null, keyword: '' })
  pagination.current = 1
  loadModuleTree()
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

function showForm(record, defaultModuleId) {
  isEdit.value = !!record
  editModuleCode.value = record ? (record.module_code || '') : ''
  if (record) {
    editId.value = record.id
    Object.assign(formState, {
      project_id: record.project_id,
      title: record.title,
      module_id: record.module_id || null,
      priority: record.priority,
      case_type: record.case_type,
      source: record.source || '',
      precondition: record.precondition || '',
      steps: record.steps || '',
      expected_result: record.expected_result,
      status: record.status,
      tags: record.tags || '',
      case_code: record.case_code || ''
    })
  } else {
    editId.value = null
    Object.assign(formState, {
      project_id: filters.project_id || null,
      title: '',
      // 从树的「+用例」入口进入时默认选中该模块
      module_id: defaultModuleId || null,
      priority: 'P1',
      case_type: 'function',
      source: '',
      precondition: '',
      steps: '',
      expected_result: '',
      status: 'draft',
      tags: '',
      case_code: ''
    })
  }
  loadModuleTree(formState.project_id)
  formVisible.value = true
}

// 弹窗内切换项目：原模块选择失效，清空并拉取新项目的模块树
function onFormProjectChange() {
  formState.module_id = null
  loadModuleTree(formState.project_id)
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
  if (!formState.title || !formState.expected_result) {
    message.warning('请填写标题和预期结果')
    return
  }
  if (!formState.module_id) {
    message.warning('请选择末级模块')
    return
  }
  const moduleNode = findModuleById(moduleTree.value, formState.module_id)
  if (!moduleNode) {
    message.warning('请选择末级模块')
    return
  }
  // 末级模块会作为 pytest 文件使用，文件名必须 test_ 开头
  if (!String(moduleNode.code || '').startsWith('test_')) {
    message.warning('该模块将作为 pytest 文件使用，请先把目录名改为 test_ 开头')
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
    refreshModuleTree()
  } finally {
    submitLoading.value = false
  }
}

async function handleDelete(id) {
  await deleteTestcase(id)
  message.success('删除成功')
  loadData()
  refreshModuleTree()
}

async function handleBatchDelete() {
  await batchDeleteTestcases(selectedRowKeys.value)
  message.success('批量删除成功')
  selectedRowKeys.value = []
  loadData()
  refreshModuleTree()
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
    refreshModuleTree()
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

// 仅当选中项目且该项目已配置自动化根路径时显示「同步用例」
const canSync = computed(() => {
  const cur = projectOptions.value.find(p => p.value === filters.project_id)
  return !!(cur && cur.auto_root_path)
})

async function handleSync() {
  if (!filters.project_id || syncing.value) return
  syncing.value = true
  try {
    const res = await syncTestcases(filters.project_id)
    message.success(res.message || '已下发同步任务，请稍后刷新查看用例情况')
    // 后台异步同步，稍后自动刷新列表与模块树
    setTimeout(() => {
      loadData()
      refreshModuleTree()
    }, 3000)
  } finally {
    setTimeout(() => { syncing.value = false }, 3000)
  }
}

onMounted(() => {
  // 进入页面时默认选中第一个项目（若有）并按项目加载模块树与列表
  loadProjects()
})
</script>

<style scoped>
.page-header {
  margin-bottom: 16px;
}
.testcase-body {
  display: flex;
  gap: 16px;
}
.module-panel {
  flex: 0 0 260px;
  width: 260px;
  min-width: 0;
  /* 兜底：超长模块名不允许把侧栏顶破，截断交给树节点内部处理 */
  overflow: hidden;
  padding: 8px;
  border: 1px solid #f0f0f0;
  border-radius: 4px;
  background: #fff;
  box-sizing: border-box;
}
/* a-table 在 flex 子项里需要 min-width: 0 才不会溢出 */
.table-panel {
  flex: 1;
  min-width: 0;
}
.readonly-text {
  color: rgba(0, 0, 0, 0.65);
}
.drawer-footer {
  margin-top: 16px;
  text-align: right;
}
/* 小屏幕下隐藏左侧模块树，保证表格可用 */
@media (max-width: 991px) {
  .module-panel {
    display: none;
  }
}
</style>
