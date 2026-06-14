<template>
  <div>
    <div class="page-header">
      <a-space>
        <a-button @click="$router.back()"><ArrowLeftOutlined /> 返回</a-button>
        <span style="font-size:16px;font-weight:600">识别结果 - 任务 #{{ taskId }}</span>
      </a-space>
    </div>

    <a-table
      :columns="columns"
      :data-source="tableData"
      :loading="loading"
      :pagination="pagination"
      row-key="id"
      @change="handleTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'detected_count'">
          <a-tag :color="record.detected_count > 0 ? 'red' : 'green'">
            {{ record.detected_count }} 个目标
          </a-tag>
        </template>
        <template v-if="column.key === 'detections'">
          <template v-if="parseDetections(record.detections).length">
            <a-tag v-for="(d, i) in parseDetections(record.detections).slice(0, 3)" :key="i" color="blue">
              {{ d.class }} {{ (d.confidence * 100).toFixed(0) }}%
            </a-tag>
            <span v-if="parseDetections(record.detections).length > 3" style="color:#999">
              +{{ parseDetections(record.detections).length - 3 }}
            </span>
          </template>
          <span v-else style="color:#999">无</span>
        </template>
        <template v-if="column.key === 'created_at'">
          {{ formatDate(record.created_at) }}
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="showImage(record, 'original')">原图</a-button>
            <a-button type="link" size="small" @click="showImage(record, 'annotated')" :disabled="!record.annotated_image_path">标注图</a-button>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="imageModalVisible"
      :title="imageModalTitle"
      :footer="null"
      width="800px"
    >
      <div style="text-align:center">
        <img :src="imageModalUrl" style="max-width:100%;max-height:70vh" />
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { ArrowLeftOutlined } from '@ant-design/icons-vue'
import { getDetectionResults, getResultImageUrl, getResultAnnotatedUrl } from '@/api/yolo'
import dayjs from 'dayjs'

const route = useRoute()
const taskId = route.params.taskId
const loading = ref(false)
const tableData = ref([])
const imageModalVisible = ref(false)
const imageModalTitle = ref('')
const imageModalUrl = ref('')

const pagination = ref({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total) => `共 ${total} 条`,
})

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '检测目标数', key: 'detected_count', width: 110 },
  { title: '识别详情', key: 'detections', width: 280 },
  { title: '时间', key: 'created_at', width: 170 },
  { title: '操作', key: 'action', width: 140 }
]

function parseDetections(str) {
  try {
    return JSON.parse(str)
  } catch { return [] }
}

function formatDate(val) {
  return val ? dayjs(val).format('YYYY-MM-DD HH:mm:ss') : '-'
}

async function loadData() {
  loading.value = true
  try {
    const res = await getDetectionResults(taskId, {
      page: pagination.value.current,
      page_size: pagination.value.pageSize,
    })
    const data = res.data || {}
    tableData.value = data.items || []
    pagination.value.total = data.total || 0
  } catch (e) {
    message.error('加载识别结果失败')
  } finally {
    loading.value = false
  }
}

function handleTableChange(pag) {
  pagination.value.current = pag.current
  pagination.value.pageSize = pag.pageSize
  loadData()
}

function showImage(record, type) {
  const token = localStorage.getItem('access_token')
  if (type === 'original') {
    imageModalTitle.value = `原图 - 结果 #${record.id}`
    imageModalUrl.value = getResultImageUrl(record.id) + '?token=' + token
  } else {
    imageModalTitle.value = `标注图 - 结果 #${record.id}`
    imageModalUrl.value = getResultAnnotatedUrl(record.id) + '?token=' + token
  }
  imageModalVisible.value = true
}

onMounted(() => loadData())
</script>
