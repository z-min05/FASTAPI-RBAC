<template>
  <div class="token-stats-page">
    <div class="page-head">
      <div class="page-title-wrap">
        <span class="page-title">Token 统计</span>
        <span class="page-sub">按当前登录用户统计</span>
      </div>
      <a-button size="small" :loading="loading" @click="loadStats">
        <ReloadOutlined /> 刷新
      </a-button>
    </div>

    <a-spin :spinning="loading">
      <template v-if="stats.summary">
        <div class="stat-cards">
          <div class="stat-card">
            <div class="stat-num">{{ stats.summary.call_count }}</div>
            <div class="stat-label">调用次数</div>
          </div>
          <div class="stat-card">
            <div class="stat-num">{{ stats.summary.total_input }}</div>
            <div class="stat-label">输入 tokens</div>
          </div>
          <div class="stat-card">
            <div class="stat-num">{{ stats.summary.total_output }}</div>
            <div class="stat-label">输出 tokens</div>
          </div>
          <div class="stat-card">
            <div class="stat-num">{{ stats.summary.total_tokens }}</div>
            <div class="stat-label">总计 tokens</div>
          </div>
        </div>

        <div v-if="stats.summary.by_model && stats.summary.by_model.length" class="stat-section">
          <div class="stat-section-title">按模型统计</div>
          <a-table
            size="small"
            row-key="model"
            :columns="modelColumns"
            :data-source="stats.summary.by_model"
            :pagination="false"
          />
        </div>

        <div class="stat-section">
          <div class="stat-section-title">调用记录</div>
          <a-table
            size="small"
            row-key="id"
            :columns="recentColumns"
            :data-source="stats.recent?.items || []"
            :pagination="pagination"
            :loading="tableLoading"
            @change="handleTableChange"
          />
        </div>
      </template>

      <a-empty v-else-if="!loading" description="暂无 Token 记录" />
    </a-spin>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import { getAgentTokenStats } from '@/api/agent'

const loading = ref(false)      // 汇总 + 首屏加载
const tableLoading = ref(false) // 翻页/改页大小时的局部加载
const stats = ref({})
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  showTotal: t => `共 ${t} 条`
})

const modelColumns = [
  { title: '模型', dataIndex: 'model' },
  { title: '次数', dataIndex: 'call_count', width: 90 },
  { title: '输入', dataIndex: 'input', width: 100 },
  { title: '输出', dataIndex: 'output', width: 100 },
  { title: '总计', dataIndex: 'total', width: 110 }
]

const recentColumns = [
  { title: '时间', dataIndex: 'created_at', width: 170, customRender: ({ text }) => formatTime(text, true) },
  { title: '模型', dataIndex: 'model' },
  { title: '轮次', dataIndex: 'step', width: 70 },
  { title: '输入', dataIndex: 'input_tokens', width: 90 },
  { title: '输出', dataIndex: 'output_tokens', width: 90 },
  { title: '总计', dataIndex: 'total_tokens', width: 100 }
]

async function loadStats() {
  if (loading.value) return
  loading.value = true
  try {
    const res = await getAgentTokenStats({
      page: pagination.current,
      page_size: pagination.pageSize
    })
    stats.value = res.data || {}
    pagination.total = stats.value.recent?.total || 0
  } catch (e) {
    // 错误已由拦截器提示
  } finally {
    loading.value = false
    tableLoading.value = false
  }
}

async function handleTableChange(pag) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  tableLoading.value = true
  try {
    const res = await getAgentTokenStats({
      page: pagination.current,
      page_size: pagination.pageSize
    })
    stats.value.recent = res.data?.recent || { items: [], total: 0 }
    pagination.total = stats.value.recent.total || 0
  } catch (e) {
    // 错误已由拦截器提示
  } finally {
    tableLoading.value = false
  }
}

function formatTime(value, withSeconds = false) {
  if (!value) return ''
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  const p = n => String(n).padStart(2, '0')
  const base = `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
  return withSeconds ? `${base}:${p(d.getSeconds())}` : base
}

onMounted(loadStats)
</script>

<style scoped>
.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.page-title-wrap {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
}

.page-sub {
  font-size: 12px;
  color: #999;
}

.stat-cards {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.stat-card {
  flex: 1;
  text-align: center;
  background: #f7f9fc;
  border-radius: 8px;
  padding: 16px 0;
}

.stat-num {
  font-size: 22px;
  font-weight: 600;
  color: #1677ff;
}

.stat-label {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

.stat-section {
  margin-bottom: 16px;
}

.stat-section-title {
  font-weight: 600;
  margin-bottom: 8px;
}
</style>
