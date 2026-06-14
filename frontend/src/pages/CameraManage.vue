<template>
  <div>
    <div class="page-header">
      <a-space>
        <a-input-search
          v-model:value="searchText"
          placeholder="搜索摄像头名称/IP"
          style="width: 260px"
          @search="loadData"
          allow-clear
        />
        <a-button type="primary" @click="showModal()">
          <PlusOutlined /> 新增摄像头
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
        <template v-if="column.key === 'is_online'">
          <a-badge :status="record.is_online ? 'success' : 'default'" :text="record.is_online ? '在线' : '离线'" />
        </template>
        <template v-if="column.key === 'is_active'">
          <a-tag :color="record.is_active ? 'green' : 'red'">
            {{ record.is_active ? '启用' : '禁用' }}
          </a-tag>
        </template>
        <template v-if="column.key === 'address'">
          {{ record.ip }}:{{ record.port }}
        </template>
        <template v-if="column.key === 'created_at'">
          {{ formatDate(record.created_at) }}
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="handleConnect(record)">
              {{ record.is_online ? '断开' : '连接' }}
            </a-button>
            <a-button type="link" size="small" @click="goLive(record)">监控</a-button>
            <a-button type="link" size="small" @click="showModal(record)">编辑</a-button>
            <a-popconfirm title="确定删除该摄像头？" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger>删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="modalVisible"
      :title="isEdit ? '编辑摄像头' : '新增摄像头'"
      @ok="handleSubmit"
      :confirm-loading="submitLoading"
      width="600px"
    >
      <a-form :model="formState" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }">
        <a-form-item label="摄像头名称" required>
          <a-input v-model:value="formState.name" placeholder="请输入摄像头名称" />
        </a-form-item>
        <a-form-item label="IP地址" required>
          <a-input v-model:value="formState.ip" placeholder="如 192.168.1.100" />
        </a-form-item>
        <a-form-item label="ONVIF端口" required>
          <a-input-number v-model:value="formState.port" :min="1" :max="65535" style="width: 100%" />
        </a-form-item>
        <a-form-item label="用户名" required>
          <a-input v-model:value="formState.username" placeholder="ONVIF用户名" />
        </a-form-item>
        <a-form-item label="密码" required>
          <a-input-password v-model:value="formState.password" placeholder="ONVIF密码" autocomplete="new-password" />
        </a-form-item>
        <a-form-item label="RTSP地址">
          <a-input v-model:value="formState.rtsp_url" placeholder="留空则自动获取" />
        </a-form-item>
        <a-form-item label="抓图URL">
          <a-input v-model:value="formState.snapshot_url" placeholder="留空则自动获取" />
        </a-form-item>
        <a-form-item label="安装位置">
          <a-input v-model:value="formState.location" placeholder="如 大门入口" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="formState.description" placeholder="请输入描述" :rows="2" />
        </a-form-item>
        <a-form-item label="状态" v-if="isEdit">
          <a-switch v-model:checked="formState.is_active" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { useRouter } from 'vue-router'
import {
  getCameras, createCamera, updateCamera, deleteCamera,
  connectCamera, disconnectCamera
} from '@/api/camera'
import dayjs from 'dayjs'

const router = useRouter()
const loading = ref(false)
const submitLoading = ref(false)
const modalVisible = ref(false)
const isEdit = ref(false)
const searchText = ref('')
const editId = ref(null)

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '名称', dataIndex: 'name', key: 'name', width: 140 },
  { title: '地址', key: 'address', width: 160 },
  { title: '位置', dataIndex: 'location', key: 'location', width: 120, ellipsis: true },
  { title: '在线状态', dataIndex: 'is_online', key: 'is_online', width: 100 },
  { title: '启用状态', dataIndex: 'is_active', key: 'is_active', width: 90 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170 },
  { title: '操作', key: 'action', width: 220, fixed: 'right' }
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
  ip: '',
  port: 80,
  username: 'admin',
  password: '',
  rtsp_url: '',
  snapshot_url: '',
  location: '',
  description: '',
  is_active: true
})

function formatDate(val) {
  return val ? dayjs(val).format('YYYY-MM-DD HH:mm:ss') : '-'
}

async function loadData() {
  loading.value = true
  try {
    const res = await getCameras({
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
      ip: record.ip,
      port: record.port,
      username: record.username,
      password: record.password,
      rtsp_url: record.rtsp_url || '',
      snapshot_url: record.snapshot_url || '',
      location: record.location || '',
      description: record.description || '',
      is_active: record.is_active
    })
  } else {
    editId.value = null
    Object.assign(formState, {
      name: '',
      ip: '',
      port: 80,
      username: 'admin',
      password: '',
      rtsp_url: '',
      snapshot_url: '',
      location: '',
      description: '',
      is_active: true
    })
  }
  modalVisible.value = true
}

async function handleSubmit() {
  submitLoading.value = true
  try {
    if (isEdit.value) {
      await updateCamera(editId.value, formState)
      message.success('更新成功')
    } else {
      await createCamera(formState)
      message.success('创建成功')
    }
    modalVisible.value = false
    loadData()
  } finally {
    submitLoading.value = false
  }
}

async function handleDelete(id) {
  await deleteCamera(id)
  message.success('删除成功')
  loadData()
}

async function handleConnect(record) {
  try {
    if (record.is_online) {
      await disconnectCamera(record.id)
      message.success('已断开连接')
    } else {
      await connectCamera(record.id)
      message.success('连接成功')
    }
    loadData()
  } catch (e) {
    // error handled by interceptor
  }
}

function goLive(record) {
  router.push(`/device/cameras/live/${record.id}`)
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
