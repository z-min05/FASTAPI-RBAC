<template>
  <div>
    <div class="page-header">
      <a-space>
        <a-input-search
          v-model:value="searchText"
          placeholder="搜索计划名称/描述"
          style="width: 240px"
          @search="loadData"
          allow-clear
        />
        <a-select
          v-model:value="projectFilter"
          placeholder="所属项目"
          style="width: 200px"
          allow-clear
          show-search
          option-filter-prop="label"
          :options="projectOptions"
          @change="loadData"
        />
        <a-select
          v-model:value="statusFilter"
          placeholder="计划状态"
          style="width: 130px"
          allow-clear
          :options="statusOptions"
          @change="loadData"
        />
        <a-button @click="handleReset">重置</a-button>
        <a-button type="primary" @click="openModal()" v-permission="'plan:create'">
          <PlusOutlined /> 新增计划
        </a-button>
      </a-space>
    </div>

    <a-table
      :columns="columns"
      :data-source="tableData"
      :loading="loading"
      :pagination="pagination"
      @change="handleTableChange"
      row-key="id"
      size="middle"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'project'">
          <span>{{ record.project_name || `#${record.project_id}` }}</span>
        </template>
        <template v-if="column.key === 'status'">
          <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
        </template>
        <template v-if="column.key === 'stats'">
          <a-space :size="4" wrap>
            <a-tag v-for="s in statsTags(record.result_stats)" :key="s.key" :color="s.color" style="margin-right: 0">
              {{ s.label }}
            </a-tag>
            <span v-if="!record.case_count" style="color: #999">暂无用例</span>
          </a-space>
        </template>
        <template v-if="column.key === 'updated_at'">
          {{ formatDate(record.updated_at) }}
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="goDetail(record.id)">进入</a-button>
            <a-button type="link" size="small" @click="openModal(record)" v-permission="'plan:update'">编辑</a-button>
            <a-popconfirm title="确定删除该测试计划？删除后计划内关联的用例记录将一并清除，用例本身不受影响。" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger v-permission="'plan:delete'">删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="modalVisible"
      :title="isEdit ? '编辑测试计划' : '新增测试计划'"
      @ok="handleSubmit"
      :confirm-loading="submitLoading"
      width="560px"
    >
      <a-form :model="formState" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }">
        <a-form-item label="计划名称" required>
          <a-input v-model:value="formState.name" placeholder="请输入计划名称" />
        </a-form-item>
        <a-form-item label="所属项目" required>
          <a-select
            v-model:value="formState.project_id"
            placeholder="请选择项目"
            style="width: 100%"
            show-search
            option-filter-prop="label"
            :options="projectOptions"
            :disabled="isEdit"
          />
        </a-form-item>
        <a-form-item label="计划状态">
          <a-select v-model:value="formState.status" :options="statusOptions" style="width: 100%" />
        </a-form-item>
        <a-form-item label="计划描述">
          <a-textarea v-model:value="formState.description" :rows="3" placeholder="请输入计划说明（测试范围/依据等）" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { getPlans, createPlan, updatePlan, deletePlan } from '@/api/plan'
import { getAllProjects } from '@/api/project'
import dayjs from 'dayjs'

const router = useRouter()
const loading = ref(false)
const submitLoading = ref(false)
const modalVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const searchText = ref('')
const projectFilter = ref(null)
const statusFilter = ref(null)
const order = ref('desc')

const statusOptions = [
  { label: '未开始', value: 'not_started' },
  { label: '进行中', value: 'in_progress' },
  { label: '已完成', value: 'completed' }
]

const columns = computed(() => [
  { title: '计划名称', dataIndex: 'name', key: 'name', width: 220, ellipsis: true },
  { title: '所属项目', dataIndex: 'project_id', key: 'project', width: 180, ellipsis: true },
  { title: '状态', dataIndex: 'status', key: 'status', width: 90 },
  { title: '用例数', dataIndex: 'case_count', key: 'case_count', width: 80 },
  { title: '执行统计', dataIndex: 'result_stats', key: 'stats', width: 260 },
  { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 170 },
  { title: '操作', key: 'action', width: 170, fixed: 'right' }
])

const tableData = ref([])
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: (total) => `共 ${total} 条`,
  showSizeChanger: true
})

const projectOptions = ref([])
const formState = reactive({
  name: '',
  project_id: null,
  status: 'not_started',
  description: ''
})

function statusLabel(status) {
  return { not_started: '未开始', in_progress: '进行中', completed: '已完成' }[status] || status || '-'
}

function statusColor(status) {
  return { not_started: 'default', in_progress: 'processing', completed: 'success' }[status] || 'default'
}

function statsTags(stats) {
  if (!stats) return []
  const defs = [
    { key: 'pass', label: '通过', color: 'success' },
    { key: 'fail', label: '失败', color: 'error' },
    { key: 'blocked', label: '阻塞', color: 'warning' },
    { key: 'skipped', label: '跳过', color: 'default' },
    { key: 'pending', label: '待执行', color: 'cyan' }
  ]
  return defs
    .filter(d => (stats[d.key] || 0) > 0)
    .map(d => ({ ...d, label: `${d.label} ${stats[d.key] || 0}` }))
}

function formatDate(val) {
  return val ? dayjs(val).format('YYYY-MM-DD HH:mm:ss') : '-'
}

async function loadProjects() {
  try {
    const res = await getAllProjects()
    projectOptions.value = (res.data || []).map(p => ({
      value: p.id,
      label: p.name
    }))
  } catch (e) {
    // 下拉加载失败不阻塞列表
  }
}

async function loadData() {
  loading.value = true
  try {
    const params = { page: pagination.current, page_size: pagination.pageSize, order: order.value }
    if (searchText.value) params.keyword = searchText.value
    if (projectFilter.value !== null && projectFilter.value !== undefined) params.project_id = projectFilter.value
    if (statusFilter.value) params.status = statusFilter.value
    const res = await getPlans(params)
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } finally {
    loading.value = false
  }
}

function handleReset() {
  searchText.value = ''
  projectFilter.value = null
  statusFilter.value = null
  pagination.current = 1
  loadData()
}

function handleTableChange(pag, _filters, sorter) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  order.value = sorter && sorter.order ? (sorter.order === 'ascend' ? 'asc' : 'desc') : 'desc'
  loadData()
}

function openModal(record) {
  isEdit.value = !!record
  if (record) {
    editId.value = record.id
    Object.assign(formState, {
      name: record.name,
      project_id: record.project_id,
      status: record.status,
      description: record.description || ''
    })
  } else {
    editId.value = null
    Object.assign(formState, {
      name: '',
      project_id: null,
      status: 'not_started',
      description: ''
    })
  }
  modalVisible.value = true
}

async function handleSubmit() {
  if (!formState.name || !formState.project_id) {
    message.warning('请填写计划名称并选择所属项目')
    return
  }
  submitLoading.value = true
  try {
    if (isEdit.value) {
      await updatePlan(editId.value, {
        name: formState.name,
        description: formState.description,
        status: formState.status
      })
      message.success('更新成功')
    } else {
      await createPlan({
        name: formState.name,
        project_id: formState.project_id,
        description: formState.description,
        status: formState.status
      })
      message.success('创建成功')
    }
    modalVisible.value = false
    loadData()
  } finally {
    submitLoading.value = false
  }
}

async function handleDelete(id) {
  await deletePlan(id)
  message.success('删除成功')
  loadData()
}

function goDetail(id) {
  router.push(`/test/plans/${id}`)
}

onMounted(() => {
  loadData()
  loadProjects()
})
</script>

<style scoped>
.page-header {
  margin-bottom: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
