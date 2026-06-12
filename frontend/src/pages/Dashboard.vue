<template>
  <div class="dashboard">
    <!-- 统计卡片 -->
    <a-row :gutter="[24, 24]">
      <a-col :span="6">
        <a-card class="stat-card" :bordered="false">
          <div class="stat-icon" style="background: #e6f7ff">
            <UserOutlined style="color: #1677ff; font-size: 28px" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.userCount }}</div>
            <div class="stat-label">用户总数</div>
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="stat-card" :bordered="false">
          <div class="stat-icon" style="background: #f6ffed">
            <TeamOutlined style="color: #52c41a; font-size: 28px" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.roleCount }}</div>
            <div class="stat-label">角色总数</div>
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="stat-card" :bordered="false">
          <div class="stat-icon" style="background: #fff7e6">
            <SafetyOutlined style="color: #faad14; font-size: 28px" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.permCount }}</div>
            <div class="stat-label">权限总数</div>
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="stat-card" :bordered="false">
          <div class="stat-icon" style="background: #fff1f0">
            <ApartmentOutlined style="color: #ff4d4f; font-size: 28px" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.deptCount }}</div>
            <div class="stat-label">部门总数</div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 图表区域 -->
    <a-row :gutter="[24, 24]" style="margin-top: 24px">
      <a-col :span="12">
        <a-card title="用户访问趋势" :bordered="false">
          <div ref="lineChartRef" style="height: 350px"></div>
        </a-card>
      </a-col>
      <a-col :span="12">
        <a-card title="角色权限分布" :bordered="false">
          <div ref="pieChartRef" style="height: 350px"></div>
        </a-card>
      </a-col>
    </a-row>

    <a-row :gutter="[24, 24]" style="margin-top: 24px">
      <a-col :span="12">
        <a-card title="各部门人数统计" :bordered="false">
          <div ref="barChartRef" style="height: 350px"></div>
        </a-card>
      </a-col>
      <a-col :span="12">
        <a-card title="操作类型统计" :bordered="false">
          <div ref="radarChartRef" style="height: 350px"></div>
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
            <a-descriptions-item label="缓存">Redis</a-descriptions-item>
          </a-descriptions>
        </a-card>
      </a-col>
      <a-col :span="8">
        <a-card title="快捷操作" :bordered="false">
          <a-space direction="vertical" style="width: 100%">
            <a-button type="primary" block @click="$router.push('/system/users')">
              <UserOutlined /> 用户管理
            </a-button>
            <a-button block @click="$router.push('/system/roles')">
              <TeamOutlined /> 角色管理
            </a-button>
            <a-button block @click="$router.push('/system/permissions')">
              <SafetyOutlined /> 权限管理
            </a-button>
            <a-button block @click="$router.push('/system/logs')">
              <FileTextOutlined /> 操作日志
            </a-button>
          </a-space>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted, onBeforeUnmount } from 'vue'
import { UserOutlined, TeamOutlined, SafetyOutlined, ApartmentOutlined, FileTextOutlined } from '@ant-design/icons-vue'
import { getUsers } from '@/api/user'
import { getRoles } from '@/api/role'
import { getPermissions } from '@/api/permission'
import { getDepartments } from '@/api/department'
import * as echarts from 'echarts'

const stats = reactive({
  userCount: 0,
  roleCount: 0,
  permCount: 0,
  deptCount: 0
})

const lineChartRef = ref(null)
const pieChartRef = ref(null)
const barChartRef = ref(null)
const radarChartRef = ref(null)

let lineChart = null
let pieChart = null
let barChart = null
let radarChart = null

// Mock 数据
const mockLineData = {
  dates: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'],
  visits: [820, 932, 901, 1234, 1290, 1330, 1520, 1430, 1650, 1890, 2100, 2340],
  activeUsers: [420, 532, 501, 734, 790, 830, 920, 830, 950, 1090, 1200, 1340]
}

const mockPieData = [
  { value: 35, name: '用户管理' },
  { value: 25, name: '角色管理' },
  { value: 20, name: '菜单管理' },
  { value: 15, name: '系统配置' },
  { value: 5, name: '其他' }
]

const mockBarData = {
  departments: ['技术部', '产品部', '运营部', '市场部', '人事部', '财务部'],
  counts: [42, 28, 35, 22, 15, 12]
}

const mockRadarData = {
  indicators: [
    { name: '查询', max: 100 },
    { name: '新增', max: 100 },
    { name: '修改', max: 100 },
    { name: '删除', max: 100 },
    { name: '导出', max: 100 },
    { name: '登录', max: 100 }
  ],
  values: [85, 60, 70, 30, 45, 90]
}

function initLineChart() {
  lineChart = echarts.init(lineChartRef.value)
  lineChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['访问量', '活跃用户'], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '12%', top: '8%', containLabel: true },
    xAxis: { type: 'category', data: mockLineData.dates, boundaryGap: false },
    yAxis: { type: 'value' },
    series: [
      {
        name: '访问量',
        type: 'line',
        smooth: true,
        data: mockLineData.visits,
        areaStyle: { opacity: 0.15 },
        itemStyle: { color: '#1677ff' }
      },
      {
        name: '活跃用户',
        type: 'line',
        smooth: true,
        data: mockLineData.activeUsers,
        areaStyle: { opacity: 0.15 },
        itemStyle: { color: '#52c41a' }
      }
    ]
  })
}

function initPieChart() {
  pieChart = echarts.init(pieChartRef.value)
  pieChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { orient: 'vertical', right: '5%', top: 'center' },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['40%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
        label: { show: false },
        emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
        data: mockPieData
      }
    ]
  })
}

function initBarChart() {
  barChart = echarts.init(barChartRef.value)
  barChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '8%', containLabel: true },
    xAxis: { type: 'category', data: mockBarData.departments },
    yAxis: { type: 'value' },
    series: [
      {
        type: 'bar',
        data: mockBarData.counts,
        barWidth: '45%',
        itemStyle: {
          borderRadius: [4, 4, 0, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#1677ff' },
            { offset: 1, color: '#69b1ff' }
          ])
        }
      }
    ]
  })
}

function initRadarChart() {
  radarChart = echarts.init(radarChartRef.value)
  radarChart.setOption({
    tooltip: {},
    radar: {
      indicator: mockRadarData.indicators,
      radius: '65%'
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: mockRadarData.values,
            name: '操作统计',
            areaStyle: { opacity: 0.2 },
            lineStyle: { color: '#1677ff' },
            itemStyle: { color: '#1677ff' }
          }
        ]
      }
    ]
  })
}

function handleResize() {
  lineChart?.resize()
  pieChart?.resize()
  barChart?.resize()
  radarChart?.resize()
}

onMounted(async () => {
  // 加载统计卡片数据
  try {
    const [users, roles, perms, depts] = await Promise.all([
      getUsers({ page: 1, page_size: 1 }),
      getRoles({ page: 1, page_size: 1 }),
      getPermissions({ page: 1, page_size: 1 }),
      getDepartments({ page: 1, page_size: 1 })
    ])
    stats.userCount = users.data.total || 0
    stats.roleCount = roles.data.total || 0
    stats.permCount = perms.data.total || 0
    stats.deptCount = depts.data.total || 0
  } catch (e) {
    // 静默处理
  }

  // 初始化图表
  initLineChart()
  initPieChart()
  initBarChart()
  initRadarChart()

  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  lineChart?.dispose()
  pieChart?.dispose()
  barChart?.dispose()
  radarChart?.dispose()
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
