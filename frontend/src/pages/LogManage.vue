<template>
  <div>
    <div class="page-header">
      <a-space>
        <a-input-search
          v-model:value="searchUsername"
          placeholder="按用户名搜索"
          style="width: 240px"
          @search="loadData"
          allow-clear
        />
        <a-select
          v-model:value="methodFilter"
          placeholder="请求方法"
          allow-clear
          style="width: 120px"
          @change="loadData"
        >
          <a-select-option value="POST">POST</a-select-option>
          <a-select-option value="PUT">PUT</a-select-option>
          <a-select-option value="DELETE">DELETE</a-select-option>
        </a-select>
      </a-space>
    </div>

    <a-table
      :columns="columns"
      :data-source="tableData"
      :loading="loading"
      :pagination="pagination"
      @change="handleTableChange"
      row-key="id"
      :scroll="{ x: 1300 }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'method'">
          <a-tag :color="methodColor(record.method)">{{ record.method }}</a-tag>
        </template>
        <template v-if="column.key === 'status_code'">
          <a-tag :color="record.status_code < 400 ? 'green' : 'red'">
            {{ record.status_code || '-' }}
          </a-tag>
        </template>
        <template v-if="column.key === 'duration'">
          {{ record.duration ? record.duration + 'ms' : '-' }}
        </template>
        <template v-if="column.key === 'created_at'">
          {{ formatDate(record.created_at) }}
        </template>
        <template v-if="column.key === 'path'">
          <a-typography-text :ellipsis="true" :content="record.path" style="max-width: 200px" />
        </template>
        <template v-if="column.key === 'action'">
          <a-button type="link" size="small" @click="showDetail(record)">详情</a-button>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="detailVisible"
      title="操作日志详情"
      width="720px"
      :footer="null"
    >
      <a-descriptions :column="2" bordered size="small">
        <a-descriptions-item label="用户">{{ currentRecord.username || '-' }}</a-descriptions-item>
        <a-descriptions-item label="IP">{{ currentRecord.ip || '-' }}</a-descriptions-item>
        <a-descriptions-item label="方法">
          <a-tag :color="methodColor(currentRecord.method)">{{ currentRecord.method }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="状态码">
          <a-tag :color="(currentRecord.status_code || 0) < 400 ? 'green' : 'red'">
            {{ currentRecord.status_code || '-' }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="路径" :span="2">{{ currentRecord.path }}</a-descriptions-item>
        <a-descriptions-item label="耗时">{{ currentRecord.duration ? currentRecord.duration + 'ms' : '-' }}</a-descriptions-item>
        <a-descriptions-item label="时间">{{ formatDate(currentRecord.created_at) }}</a-descriptions-item>
      </a-descriptions>

      <div style="margin-top: 16px">
        <div class="detail-label">请求内容：</div>
        <a-typography-paragraph>
          <pre class="json-block">{{ formatJson(currentRecord.params) }}</pre>
        </a-typography-paragraph>
      </div>

      <div style="margin-top: 12px">
        <div class="detail-label">响应内容：</div>
        <a-typography-paragraph>
          <pre class="json-block">{{ formatJson(currentRecord.response) }}</pre>
        </a-typography-paragraph>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { getLogs } from '@/api/log'
import dayjs from 'dayjs'

const loading = ref(false)
const searchUsername = ref('')
const methodFilter = ref(null)
const detailVisible = ref(false)
const currentRecord = ref({})
// 时间排序：默认倒序（最新在前）
const order = ref('desc')

const columns = computed(() => [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '用户', dataIndex: 'username', key: 'username', width: 100 },
  { title: '方法', dataIndex: 'method', key: 'method', width: 80 },
  { title: '路径', dataIndex: 'path', key: 'path', width: 200 },
  { title: '状态码', dataIndex: 'status_code', key: 'status_code', width: 80 },
  { title: 'IP', dataIndex: 'ip', key: 'ip', width: 130 },
  { title: '耗时', dataIndex: 'duration', key: 'duration', width: 80 },
  {
    title: '时间',
    dataIndex: 'created_at',
    key: 'created_at',
    width: 180,
    sorter: true,
    sortDirections: ['descend', 'ascend'],
    sortOrder: order.value === 'asc' ? 'ascend' : 'descend'
  },
  { title: '操作', key: 'action', width: 80, fixed: 'right' }
])

const tableData = ref([])
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: (total) => `共 ${total} 条`,
  showSizeChanger: true
})

function methodColor(method) {
  const map = { GET: 'blue', POST: 'green', PUT: 'orange', DELETE: 'red' }
  return map[method] || 'default'
}

function formatDate(val) {
  return val ? dayjs(val).format('YYYY-MM-DD HH:mm:ss') : '-'
}

function formatJson(str) {
  if (!str) return '-'
  try {
    return JSON.stringify(JSON.parse(str), null, 2)
  } catch {
    return str
  }
}

function showDetail(record) {
  currentRecord.value = record
  detailVisible.value = true
}

async function loadData() {
  loading.value = true
  try {
    const res = await getLogs({
      page: pagination.current,
      page_size: pagination.pageSize,
      order: order.value
    })
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } finally {
    loading.value = false
  }
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

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.page-header {
  margin-bottom: 16px;
}
.detail-label {
  font-weight: 600;
  margin-bottom: 4px;
  color: rgba(0, 0, 0, 0.85);
}
.json-block {
  background: #f5f5f5;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  padding: 12px;
  max-height: 300px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
  margin: 0;
}
</style>
