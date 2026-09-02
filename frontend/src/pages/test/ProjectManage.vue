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
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="showModal(record)" v-permission="'project:update'">编辑</a-button>
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
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { getProjects, createProject, updateProject, deleteProject, getOwnerOptions } from '@/api/project'
import dayjs from 'dayjs'

const loading = ref(false)
const submitLoading = ref(false)
const modalVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const searchText = ref('')
const statusFilter = ref(null)
const statusOptions = [
  { label: '启用', value: true },
  { label: '停用', value: false }
]

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '编码', dataIndex: 'code', key: 'code', width: 120 },
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '负责人', dataIndex: 'owner_id', key: 'owner', width: 120 },
  { title: '状态', dataIndex: 'is_active', key: 'is_active', width: 80 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: '操作', key: 'action', width: 140, fixed: 'right' }
]

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

const formState = reactive({
  code: '',
  name: '',
  description: '',
  owner_id: null,
  is_active: true
})

function formatDate(val) {
  return val ? dayjs(val).format('YYYY-MM-DD HH:mm:ss') : '-'
}

function onSelectChange(keys) {
  selectedRowKeys.value = keys
}

async function loadData() {
  loading.value = true
  try {
    const params = { page: pagination.current, page_size: pagination.pageSize }
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

function handleTableChange(pag) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadData()
}

function showModal(record) {
  isEdit.value = !!record
  if (record) {
    editId.value = record.id
    Object.assign(formState, {
      code: record.code,
      name: record.name,
      description: record.description || '',
      owner_id: record.owner_id,
      is_active: record.is_active
    })
  } else {
    editId.value = null
    Object.assign(formState, {
      code: '',
      name: '',
      description: '',
      owner_id: null,
      is_active: true
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
    if (isEdit.value) {
      await updateProject(editId.value, { ...formState })
      message.success('更新成功')
    } else {
      await createProject({ ...formState })
      message.success('创建成功')
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
