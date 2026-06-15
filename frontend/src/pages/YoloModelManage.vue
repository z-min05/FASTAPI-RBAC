<template>
  <div>
    <div class="page-header">
      <a-space>
        <a-input-search
          v-model:value="searchText"
          placeholder="搜索模型名称/版本"
          style="width: 260px"
          @search="loadData"
          allow-clear
        />
        <a-button type="primary" @click="showModal()">
          <PlusOutlined /> 新增模型
        </a-button>
        <a-button @click="$router.push('/device/yolo/tasks')">
          <AimOutlined /> 识别任务
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
        <template v-if="column.key === 'classes'">
          <a-tag v-for="(cls, i) in parseClasses(record.classes)" :key="i" color="blue">{{ cls }}</a-tag>
        </template>
        <template v-if="column.key === 'is_active'">
          <a-tag :color="record.is_active ? 'green' : 'red'">{{ record.is_active ? '启用' : '禁用' }}</a-tag>
        </template>
        <template v-if="column.key === 'created_at'">
          {{ formatDate(record.created_at) }}
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="showModal(record)">编辑</a-button>
            <a-popconfirm title="确定删除该模型？" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger>删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="modalVisible"
      :title="isEdit ? '编辑YOLO模型' : '新增YOLO模型'"
      @ok="handleSubmit"
      :confirm-loading="submitLoading"
      width="600px"
    >
      <a-form :model="formState" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }">
        <a-form-item label="模型名称" required>
          <a-input v-model:value="formState.name" placeholder="如 YOLOv8n 通用检测" />
        </a-form-item>
        <a-form-item label="模型版本" required>
          <a-input v-model:value="formState.version" placeholder="如 yolov8n, yolov8s" />
        </a-form-item>
        <a-form-item label="模型文件" :required="!isEdit">
          <a-upload
            :file-list="fileList"
            :before-upload="beforeUpload"
            :max-count="1"
            accept=".pt"
            @remove="handleRemoveFile"
          >
            <a-button><UploadOutlined /> 选择模型文件(.pt)</a-button>
          </a-upload>
          <div v-if="isEdit && !fileList.length" style="font-size:12px;color:#999;margin-top:4px">
            当前文件: {{ formState.file_path?.split(/[/\\]/).pop() }}，不上传新文件则保留原文件
          </div>
        </a-form-item>
        <a-form-item label="识别类别" required>
          <a-textarea v-model:value="formState.classes" placeholder='如 ["person","car","dog"]' :rows="4" />
          <div style="font-size:12px;color:#999;margin-top:4px">JSON数组格式，表示模型可识别的类别</div>
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="formState.description" placeholder="模型描述" :rows="2" />
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
import { PlusOutlined, AimOutlined, UploadOutlined } from '@ant-design/icons-vue'
import { getYoloModels, createYoloModel, updateYoloModel, deleteYoloModel } from '@/api/yolo'
import dayjs from 'dayjs'

const loading = ref(false)
const submitLoading = ref(false)
const modalVisible = ref(false)
const isEdit = ref(false)
const searchText = ref('')
const editId = ref(null)
const fileList = ref([])

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '名称', dataIndex: 'name', key: 'name', width: 160 },
  { title: '版本', dataIndex: 'version', key: 'version', width: 100 },
  { title: '识别类别', key: 'classes', width: 240 },
  { title: '状态', dataIndex: 'is_active', key: 'is_active', width: 80 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170 },
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
  version: '',
  file_path: '',
  classes: '',
  description: '',
  is_active: true
})

function parseClasses(str) {
  try {
    const arr = JSON.parse(str)
    return Array.isArray(arr) ? arr.slice(0, 5) : [str]
  } catch { return [str] }
}

function formatDate(val) {
  return val ? dayjs(val).format('YYYY-MM-DD HH:mm:ss') : '-'
}

function beforeUpload(file) {
  fileList.value = [file]
  return false // 阻止自动上传，手动提交
}

function handleRemoveFile() {
  fileList.value = []
}

async function loadData() {
  loading.value = true
  try {
    const res = await getYoloModels({
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
  fileList.value = []
  if (record) {
    editId.value = record.id
    Object.assign(formState, {
      name: record.name,
      version: record.version,
      file_path: record.file_path,
      classes: record.classes,
      description: record.description || '',
      is_active: record.is_active
    })
  } else {
    editId.value = null
    Object.assign(formState, {
      name: '',
      version: '',
      file_path: '',
      classes: '',
      description: '',
      is_active: true
    })
  }
  modalVisible.value = true
}

async function handleSubmit() {
  if (!formState.name || !formState.version || !formState.classes) {
    message.warning('请填写必填项')
    return
  }
  if (!isEdit.value && !fileList.value.length) {
    message.warning('请选择模型文件')
    return
  }

  submitLoading.value = true
  try {
    const formData = new FormData()
    formData.append('name', formState.name)
    formData.append('version', formState.version)
    formData.append('classes', formState.classes)
    if (formState.description) {
      formData.append('description', formState.description)
    }
    if (fileList.value.length) {
      formData.append('file', fileList.value[0])
    }
    if (isEdit.value) {
      formData.append('is_active', String(formState.is_active))
      await updateYoloModel(editId.value, formData)
      message.success('更新成功')
    } else {
      await createYoloModel(formData)
      message.success('创建成功')
    }
    modalVisible.value = false
    loadData()
  } catch (e) {
    message.error(e.response?.data?.message || '操作失败')
  } finally {
    submitLoading.value = false
  }
}

async function handleDelete(id) {
  try {
    await deleteYoloModel(id)
    message.success('删除成功')
    loadData()
  } catch (e) {
    message.error(e.response?.data?.message || '删除失败')
  }
}

onMounted(() => loadData())
</script>
