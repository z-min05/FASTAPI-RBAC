<template>
  <div>
    <div class="page-header">
      <a-space>
        <a-input-search
          v-model:value="searchText"
          placeholder="搜索权限名称"
          style="width: 240px"
          @search="loadData"
          allow-clear
        />
        <a-button type="primary" @click="showModal()">
          <PlusOutlined /> 新增权限
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
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'module'">
          <a-tag v-if="record.module" color="blue">{{ record.module }}</a-tag>
          <span v-else>-</span>
        </template>
        <template v-if="column.key === 'action_tag'">
          <a-tag v-if="record.action" color="orange">{{ record.action }}</a-tag>
          <span v-else>-</span>
        </template>
        <template v-if="column.key === 'code'">
          <a-typography-text code>{{ record.code }}</a-typography-text>
        </template>
        <template v-if="column.key === 'created_at'">
          {{ formatDate(record.created_at) }}
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="showModal(record)">编辑</a-button>
            <a-popconfirm title="确定删除该权限？" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger>删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="modalVisible"
      :title="isEdit ? '编辑权限' : '新增权限'"
      @ok="handleSubmit"
      :confirm-loading="submitLoading"
    >
      <a-form :model="formState" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }">
        <a-form-item label="权限名称" required>
          <a-input v-model:value="formState.name" placeholder="请输入权限名称" />
        </a-form-item>
        <a-form-item label="权限编码" required>
          <a-input v-model:value="formState.code" placeholder="如: user:list" />
        </a-form-item>
        <a-form-item label="所属模块">
          <a-input v-model:value="formState.module" placeholder="如: user" />
        </a-form-item>
        <a-form-item label="操作类型">
          <a-select v-model:value="formState.action" placeholder="请选择" allow-clear>
            <a-select-option value="list">列表</a-select-option>
            <a-select-option value="detail">详情</a-select-option>
            <a-select-option value="create">创建</a-select-option>
            <a-select-option value="update">更新</a-select-option>
            <a-select-option value="delete">删除</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="formState.description" placeholder="请输入描述" :rows="3" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { getPermissions, createPermission, updatePermission, deletePermission } from '@/api/permission'
import dayjs from 'dayjs'

const loading = ref(false)
const submitLoading = ref(false)
const modalVisible = ref(false)
const isEdit = ref(false)
const searchText = ref('')
const editId = ref(null)

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '权限名称', dataIndex: 'name', key: 'name' },
  { title: '权限编码', dataIndex: 'code', key: 'code' },
  { title: '模块', dataIndex: 'module', key: 'module', width: 100 },
  { title: '操作', dataIndex: 'action', key: 'action_tag', width: 100 },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
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

const formState = reactive({
  name: '',
  code: '',
  module: '',
  action: null,
  description: ''
})

function formatDate(val) {
  return val ? dayjs(val).format('YYYY-MM-DD HH:mm:ss') : '-'
}

async function loadData() {
  loading.value = true
  try {
    const res = await getPermissions({
      page: pagination.current,
      page_size: pagination.pageSize
    })
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } finally {
    loading.value = false
  }
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
      name: record.name,
      code: record.code,
      module: record.module || '',
      action: record.action || null,
      description: record.description || ''
    })
  } else {
    editId.value = null
    Object.assign(formState, {
      name: '',
      code: '',
      module: '',
      action: null,
      description: ''
    })
  }
  modalVisible.value = true
}

async function handleSubmit() {
  submitLoading.value = true
  try {
    if (isEdit.value) {
      await updatePermission(editId.value, formState)
      message.success('更新成功')
    } else {
      await createPermission(formState)
      message.success('创建成功')
    }
    modalVisible.value = false
    loadData()
  } finally {
    submitLoading.value = false
  }
}

async function handleDelete(id) {
  await deletePermission(id)
  message.success('删除成功')
  loadData()
}

onMounted(() => {
  loadData()
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
