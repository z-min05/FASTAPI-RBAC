<template>
  <div class="dashboard">
    <!-- 统计卡片 -->
    <a-row :gutter="[24, 24]">
      <a-col :span="6">
        <a-card class="stat-card" :bordered="false">
          <div class="stat-icon" style="background: #e6f7ff">
            <FileTextOutlined style="color: #1677ff; font-size: 28px" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.planCount }}</div>
            <div class="stat-label">测试计划总数</div>
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="stat-card" :bordered="false">
          <div class="stat-icon" style="background: #f6ffed">
            <CheckCircleOutlined style="color: #52c41a; font-size: 28px" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.caseCount }}</div>
            <div class="stat-label">测试用例总数</div>
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="stat-card" :bordered="false">
          <div class="stat-icon" style="background: #fff7e6">
            <PlayCircleOutlined style="color: #faad14; font-size: 28px" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.executedCount }}</div>
            <div class="stat-label">计划执行总次数</div>
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="stat-card" :bordered="false">
          <div class="stat-icon" style="background: #fff1f0">
            <ClockCircleOutlined style="color: #ff4d4f; font-size: 28px" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.todayCount }}</div>
            <div class="stat-label">今日执行次数</div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 图表区域 -->
    <a-row :gutter="[24, 24]" style="margin-top: 24px">
      <a-col :span="12">
        <a-card title="各计划用例分布" :bordered="false">
          <div ref="piePlanRef" style="height: 350px"></div>
        </a-card>
      </a-col>
      <a-col :span="12">
        <a-card title="测试结果分布" :bordered="false">
          <div ref="pieResultRef" style="height: 350px"></div>
        </a-card>
      </a-col>
    </a-row>

    <a-row :gutter="[24, 24]" style="margin-top: 24px">
      <a-col :span="12">
        <a-card title="近7日执行趋势" :bordered="false">
          <div ref="lineTrendRef" style="height: 350px"></div>
        </a-card>
      </a-col>
      <a-col :span="12">
        <a-card title="各模块用例统计" :bordered="false">
          <div ref="barModuleRef" style="height: 350px"></div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 下方区域 -->
    <a-row :gutter="24" style="margin-top: 24px">
      <a-col :span="16">
        <a-card title="系统信息" :bordered="false">
          <a-descriptions :column="2" bordered size="small">
            <a-descriptions-item label="系统名称">RBAC 管理系统</a-descriptions-item>
            <a-descriptions-item label="系统版本">1.0.0</a-descriptions-item>
            <a-descriptions-item label="前端框架">Vue 3 + Ant Design Vue</a-descriptions-item>
            <a-descriptions-item label="后端框架">FastAPI</a-descriptions-item>
            <a-descriptions-item label="数据库">PostgreSQL</a-descriptions-item>
          </a-descriptions>
        </a-card>
      </a-col>
      <a-col :span="8">
        <a-card title="快捷操作" :bordered="false">
          <a-space direction="vertical" style="width: 100%">
            <a-button type="primary" block @click="$router.push('/test/plans')">
              <FileTextOutlined /> 测试计划
            </a-button>
            <a-button block @click="$router.push('/test/testcases')">
              <CheckCircleOutlined /> 测试用例
            </a-button>
          </a-space>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted, onBeforeUnmount } from 'vue'
import {
  FileTextOutlined, CheckCircleOutlined,
  PlayCircleOutlined, ClockCircleOutlined,
} from '@ant-design/icons-vue'
import { getDashboardStats } from '@/api/dashboard'
import * as echarts from 'echarts'

const stats = reactive({
  planCount: 0,
  caseCount: 0,
  executedCount: 0,
  todayCount: 0,
})

const piePlanRef = ref(null)
const pieResultRef = ref(null)
const lineTrendRef = ref(null)
const barModuleRef = ref(null)

let piePlanChart = null
let pieResultChart = null
let lineTrendChart = null
let barModuleChart = null

const resultColorMap = {
  '通过': '#52c41a',
  '失败': '#ff4d4f',
  '阻塞': '#faad14',
  '跳过': '#1677ff',
  '执行中': '#722ed1',
}

function initPiePlanChart(planDistribution) {
  piePlanChart = echarts.init(piePlanRef.value)
  piePlanChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { orient: 'vertical', right: '5%', top: 'center' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['40%', '50%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
      data: planDistribution.length > 0 ? planDistribution : [{ name: '暂无数据', value: 1 }],
    }],
  })
}

function initPieResultChart(resultDistribution) {
  pieResultChart = echarts.init(pieResultRef.value)
  const data = resultDistribution.length > 0 ? resultDistribution : [{ name: '暂无数据', value: 1 }]
  pieResultChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { orient: 'vertical', right: '5%', top: 'center' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['40%', '50%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
      data: data.map(item => ({
        ...item,
        itemStyle: { color: resultColorMap[item.name] || '#1677ff' },
      })),
    }],
  })
}

function initLineTrendChart(dailyTrend) {
  lineTrendChart = echarts.init(lineTrendRef.value)
  lineTrendChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '8%', containLabel: true },
    xAxis: { type: 'category', data: dailyTrend.map(d => d.date), boundaryGap: false },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{
      name: '执行次数',
      type: 'line',
      smooth: true,
      data: dailyTrend.map(d => d.count),
      areaStyle: { opacity: 0.15 },
      itemStyle: { color: '#1677ff' },
    }],
  })
}

function initBarModuleChart(moduleDistribution) {
  barModuleChart = echarts.init(barModuleRef.value)
  barModuleChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '8%', containLabel: true },
    xAxis: {
      type: 'category',
      data: moduleDistribution.map(m => m.name),
      axisLabel: { rotate: moduleDistribution.length > 5 ? 30 : 0 },
    },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{
      type: 'bar',
      data: moduleDistribution.map(m => m.value),
      barWidth: '45%',
      itemStyle: {
        borderRadius: [4, 4, 0, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#1677ff' },
          { offset: 1, color: '#69b1ff' },
        ]),
      },
    }],
  })
}

function handleResize() {
  piePlanChart?.resize()
  pieResultChart?.resize()
  lineTrendChart?.resize()
  barModuleChart?.resize()
}

onMounted(async () => {
  let chartData = null
  try {
    const res = await getDashboardStats()
    if (res.code === 200 && res.data) {
      const d = res.data
      stats.planCount = d.planCount || 0
      stats.caseCount = d.caseCount || 0
      stats.executedCount = d.executedCount || 0
      stats.todayCount = d.todayCount || 0
      chartData = d
    }
  } catch (e) {
    // 静默处理
  }

  const planDistribution = chartData?.planDistribution || []
  const resultDistribution = chartData?.resultDistribution || []
  const dailyTrend = chartData?.dailyTrend || []
  const moduleDistribution = chartData?.moduleDistribution || []

  initPiePlanChart(planDistribution)
  initPieResultChart(resultDistribution)
  initLineTrendChart(dailyTrend)
  initBarModuleChart(moduleDistribution)

  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  piePlanChart?.dispose()
  pieResultChart?.dispose()
  lineTrendChart?.dispose()
  barModuleChart?.dispose()
})
</script>

<style scoped>
.stat-card {
  display: flex;
  align-items: center;
}

.stat-card :deep(.ant-card-body) {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 24px;
  width: 100%;
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.85);
  line-height: 1.2;
}

.stat-label {
  font-size: 14px;
  color: rgba(0, 0, 0, 0.45);
  margin-top: 4px;
}
</style>