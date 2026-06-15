<template>
  <div>
    <div class="page-header">
      <a-space>
        <a-input-search
          v-model:value="searchText"
          placeholder="搜索任务名称"
          style="width: 260px"
          @search="loadData"
          allow-clear
        />
        <a-button type="primary" @click="showModal()">
          <PlusOutlined /> 新增任务
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
        <template v-if="column.key === 'target_classes'">
          <a-tag v-for="(cls, i) in parseClasses(record.target_classes)" :key="i" color="orange">{{ cls }}</a-tag>
        </template>
        <template v-if="column.key === 'confidence'">
          {{ (record.confidence * 100).toFixed(0) }}%
        </template>
        <template v-if="column.key === 'is_active'">
          <a-badge :status="record.is_active ? 'processing' : 'default'" :text="record.is_active ? '运行中' : '已停止'" />
        </template>
        <template v-if="column.key === 'last_run_at'">
          {{ record.last_run_at || '-' }}
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="handleToggle(record)">
              {{ record.is_active ? '停止' : '启动' }}
            </a-button>
            <a-button type="link" size="small" @click="handleRunOnce(record)" :disabled="record.is_active">执行</a-button>
            <a-button type="link" size="small" @click="viewResults(record)">结果</a-button>
            <a-button type="link" size="small" @click="showModal(record)">编辑</a-button>
            <a-popconfirm title="确定删除该任务？" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger>删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="modalVisible"
      :title="isEdit ? '编辑识别任务' : '新增识别任务'"
      @ok="handleSubmit"
      :confirm-loading="submitLoading"
      width="600px"
    >
      <a-form :model="formState" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }">
        <a-form-item label="任务名称" required>
          <a-input v-model:value="formState.name" placeholder="如 大门人员检测" />
        </a-form-item>
        <a-form-item label="摄像头" required>
          <a-select v-model:value="formState.camera_id" placeholder="选择摄像头" :loading="cameraLoading">
            <a-select-option v-for="cam in cameraList" :key="cam.id" :value="cam.id">
              {{ cam.name }} ({{ cam.ip }})
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="YOLO模型" required>
          <a-select v-model:value="formState.model_id" placeholder="选择模型" :loading="modelLoading">
            <a-select-option v-for="m in modelList" :key="m.id" :value="m.id">
              {{ m.name }} ({{ m.version }})
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="目标类别" required>
          <a-textarea v-model:value="formState.target_classes" placeholder='如 ["person","car"]' :rows="3" />
          <div style="font-size:12px;color:#999;margin-top:4px">JSON数组格式，为空则识别所有类别</div>
        </a-form-item>
        <a-form-item label="置信度阈值">
          <a-slider v-model:value="formState.confidence" :min="0.01" :max="1" :step="0.01" :marks="{ 0.25: '25%', 0.5: '50%', 0.75: '75%', 1: '100%' }" />
        </a-form-item>
        <a-form-item label="识别间隔(秒)" required>
          <a-input-number v-model:value="formState.interval_seconds" :min="5" :max="3600" style="width: 100%" />
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
  getDetectionTasks, createDetectionTask, updateDetectionTask,
  deleteDetectionTask, toggleDetectionTask, runDetectionOnce
} from '@/api/yolo'
import { getYoloModels } from '@/api/yolo'
import { getCameras } from '@/api/camera'

const router = useRouter()
const loading = ref(false)
const submitLoading = ref(false)
const modalVisible = ref(false)
const isEdit = ref(false)
const searchText = ref('')
const editId = ref(null)
const cameraLoading = ref(false)
const modelLoading = ref(false)
const cameraList = ref([])
const modelList = ref([])

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '名称', dataIndex: 'name', key: 'name', width: 140 },
  { title: '目标类别', key: 'target_classes', width: 180 },
  { title: '置信度', key: 'confidence', width: 80 },
  { title: '间隔(秒)', dataIndex: 'interval_seconds', key: 'interval_seconds', width: 90 },
  { title: '状态', key: 'is_active', width: 100 },
  { title: '上次执行', key: 'last_run_at', width: 170 },
  { title: '操作', key: 'action', width: 260, fixed: 'right' }
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
  camera_id: null,
  model_id: null,
  target_classes: '',
  confidence: 0.5,
  interval_seconds: 30
})

function parseClasses(str) {
  try {
    const arr = JSON.parse(str)
    return Array.isArray(arr) ? arr.slice(0, 5) : [str]
  } catch { return [str] }
}

async function loadData() {
  loading.value = true
  try {
    const res = await getDetectionTasks({
      page: pagination.current,
      page_size: pagination.pageSize
    })
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } finally {
    loading.value = false
  }
}

async function loadCameras() {
  cameraLoading.value = true
  try {
    const res = await getCameras({ page: 1, page_size: 100 })
    cameraList.value = res.data.items || []
  } finally {
    cameraLoading.value = false
  }
}

async function loadModels() {
  modelLoading.value = true
  try {
    const res = await getYoloModels({ page: 1, page_size: 100 })
    modelList.value = res.data.items || []
  } finally {
    modelLoading.value = false
  }
}

function handleTableChange(pag) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadData()
}

function showModal(record) {
  isEdit.value = !!record
  loadCameras()
  loadModels()
  if (record) {
    editId.value = record.id
    Object.assign(formState, {
      name: record.name,
      camera_id: record.camera_id,
      model_id: record.model_id,
      target_classes: record.target_classes,
      confidence: record.confidence || 0.5,
      interval_seconds: record.interval_seconds
    })
  } else {
    editId.value = null
    Object.assign(formState, {
      name: '',
      camera_id: null,
      model_id: null,
      target_classes: '',
      confidence: 0.5,
      interval_seconds: 30
    })
  }
  modalVisible.value = true
}

async function handleSubmit() {
  if (!formState.name || !formState.camera_id || !formState.model_id || !formState.target_classes) {
    message.warning('请填写必填项')
    return
  }
  submitLoading.value = true
  try {
    if (isEdit.value) {
      await updateDetectionTask(editId.value, formState)
      message.success('更新成功')
    } else {
      await createDetectionTask(formState)
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

async function handleToggle(record) {
  try {
    await toggleDetectionTask(record.id, !record.is_active)
    message.success(record.is_active ? '已停止' : '已启动')
    loadData()
  } catch (e) {
    message.error(e.response?.data?.message || '操作失败')
  }
}

async function handleRunOnce(record) {
  try {
    message.loading({ content: '正在执行识别...', key: 'run', duration: 0 })
    await runDetectionOnce(record.id)
    message.success({ content: '识别完成', key: 'run' })
    loadData()
  } catch (e) {
    message.error({ content: e.response?.data?.message || '识别失败', key: 'run' })
  }
}

function viewResults(record) {
  router.push(`/device/yolo/results/${record.id}`)
}

async function handleDelete(id) {
  try {
    await deleteDetectionTask(id)
    message.success('删除成功')
    loadData()
  } catch (e) {
    message.error(e.response?.data?.message || '删除失败')
  }
}

onMounted(() => loadData())
</script>
