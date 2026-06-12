<template>
  <div class="big-screen">
    <!-- 全屏 Leaflet 瓦片地图背景 -->
    <div ref="mapRef" class="map-bg"></div>

    <!-- 顶部标题栏 -->
    <header class="screen-header">
      <div class="header-side left">
        <div class="header-wing"></div>
        <div class="header-line"></div>
      </div>
      <div class="header-center" @click="$router.push('/dashboard')">
        <div class="header-frame">
          <span class="corner tl"></span>
          <span class="corner tr"></span>
          <span class="corner bl"></span>
          <span class="corner br"></span>
          <h1 class="header-title">智慧政务数据大屏</h1>
          <div class="header-time">{{ currentTime }}</div>
        </div>
      </div>
      <div class="header-side right">
        <div class="header-line"></div>
        <button class="toggle-all-btn" @click="toggleAll" :title="allCollapsed ? '展开全部' : '收回全部'">
          <FullscreenOutlined v-if="allCollapsed" />
          <FullscreenExitOutlined v-else />
        </button>
        <div class="header-wing"></div>
      </div>
    </header>

    <!-- 主体内容 -->
    <div class="screen-body">
      <!-- 左侧面板 -->
      <div class="side-col left-col">
        <div class="card-wrap" :class="{ collapsed: collapsed.left1 }">
          <div class="card">
            <div class="card-header">
              <span class="title-dot"></span>部门人员统计
            </div>
            <div class="card-body"><div ref="leftBarRef" class="chart-box"></div></div>
          </div>
          <button class="toggle-btn" @click="collapsed.left1 = !collapsed.left1">
            <LeftOutlined v-if="!collapsed.left1" /><RightOutlined v-else />
          </button>
        </div>
        <div class="card-wrap" :class="{ collapsed: collapsed.left2 }">
          <div class="card">
            <div class="card-header">
              <span class="title-dot"></span>业务类型分布
            </div>
            <div class="card-body"><div ref="leftPieRef" class="chart-box"></div></div>
          </div>
          <button class="toggle-btn" @click="collapsed.left2 = !collapsed.left2">
            <LeftOutlined v-if="!collapsed.left2" /><RightOutlined v-else />
          </button>
        </div>
      </div>

      <!-- 中间地图区域 -->
      <div class="center-area"></div>

      <!-- 右侧面板 -->
      <div class="side-col right-col">
        <div class="card-wrap" :class="{ collapsed: collapsed.right1 }">
          <div class="card">
            <div class="card-header">
              <span class="title-dot"></span>数据概览
            </div>
            <div class="card-body">
              <div class="stats-grid">
                <div class="stat-item"><div class="stat-num cyan">{{ animatedStats.totalUsers }}</div><div class="stat-desc">注册用户</div></div>
                <div class="stat-item"><div class="stat-num green">{{ animatedStats.onlineUsers }}</div><div class="stat-desc">在线用户</div></div>
                <div class="stat-item"><div class="stat-num yellow">{{ animatedStats.todayVisits }}</div><div class="stat-desc">今日访问</div></div>
                <div class="stat-item"><div class="stat-num red">{{ animatedStats.totalOps }}</div><div class="stat-desc">操作总量</div></div>
              </div>
            </div>
          </div>
          <button class="toggle-btn" @click="collapsed.right1 = !collapsed.right1">
            <RightOutlined v-if="!collapsed.right1" /><LeftOutlined v-else />
          </button>
        </div>
        <div class="card-wrap" :class="{ collapsed: collapsed.right2 }">
          <div class="card">
            <div class="card-header">
              <span class="title-dot"></span>实时操作日志
            </div>
            <div class="card-body">
              <div class="log-list">
                <div class="log-row log-header"><span>时间</span><span>用户</span><span>操作</span><span>状态</span></div>
                <div v-for="(log, idx) in logList" :key="idx" class="log-row" :class="{ 'log-new': log.isNew }">
                  <span>{{ log.time }}</span><span>{{ log.user }}</span><span>{{ log.action }}</span>
                  <span :class="log.status === '成功' ? 'status-ok' : 'status-fail'">{{ log.status }}</span>
                </div>
              </div>
            </div>
          </div>
          <button class="toggle-btn" @click="collapsed.right2 = !collapsed.right2">
            <RightOutlined v-if="!collapsed.right2" /><LeftOutlined v-else />
          </button>
        </div>
      </div>

      <!-- 底部折线图卡片（夹在左右之间） -->
      <div class="bottom-card" :class="{ collapsed: collapsed.bottom }">
        <div class="card">
          <div class="card-header">
            <span class="title-dot"></span>访问趋势
          </div>
          <div class="card-body"><div ref="rightLineRef" class="chart-box"></div></div>
        </div>
        <button class="toggle-btn" @click="collapsed.bottom = !collapsed.bottom">
          <DownOutlined v-if="!collapsed.bottom" /><UpOutlined v-else />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import {
  LeftOutlined, RightOutlined, UpOutlined, DownOutlined,
  FullscreenOutlined, FullscreenExitOutlined
} from '@ant-design/icons-vue'
import * as echarts from 'echarts'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

const leftBarRef = ref(null)
const leftPieRef = ref(null)
const mapRef = ref(null)
const rightLineRef = ref(null)

let leftBarChart = null
let leftPieChart = null
let rightLineChart = null
let map = null
let timer = null
let logTimer = null

const currentTime = ref('')
const animatedStats = reactive({ totalUsers: 0, onlineUsers: 0, todayVisits: 0, totalOps: 0 })

// ---- 卡片收回状态 ----
const collapsed = reactive({
  left1: false, left2: false,
  right1: false, right2: false,
  bottom: false
})

const allCollapsed = computed(() =>
  collapsed.left1 && collapsed.left2 && collapsed.right1 && collapsed.right2 && collapsed.bottom
)

function toggleAll() {
  const target = !allCollapsed.value
  collapsed.left1 = target
  collapsed.left2 = target
  collapsed.right1 = target
  collapsed.right2 = target
  collapsed.bottom = target
}

// ---- 配色 ----
const cyanColor = '#00e5ff'
const greenColor = '#00ff88'
const yellowColor = '#ffcc00'
const redColor = '#ff4d6a'
const textColor = '#a0cfff'
const axisLineColor = '#1a3a5c'

// ---- Mock 数据 ----
const mockBarData = {
  departments: ['技术部', '产品部', '运营部', '市场部', '人事部', '财务部', '法务部', '行政部'],
  counts: [42, 28, 35, 22, 15, 12, 8, 18]
}

const mockPieData = [
  { value: 35, name: '用户管理' },
  { value: 25, name: '审批流程' },
  { value: 18, name: '数据查询' },
  { value: 12, name: '公文流转' },
  { value: 10, name: '系统配置' }
]

const mockMapPoints = [
  { name: '北京', value: 1280, lat: 39.92, lng: 116.46 },
  { name: '上海', value: 960, lat: 31.22, lng: 121.48 },
  { name: '广东', value: 1120, lat: 23.16, lng: 113.23 },
  { name: '浙江', value: 880, lat: 30.26, lng: 120.19 },
  { name: '江苏', value: 820, lat: 32.04, lng: 118.78 },
  { name: '四川', value: 650, lat: 30.67, lng: 104.06 },
  { name: '湖北', value: 580, lat: 30.52, lng: 114.31 },
  { name: '山东', value: 720, lat: 36.65, lng: 117.00 },
  { name: '河南', value: 540, lat: 34.76, lng: 113.65 },
  { name: '福建', value: 460, lat: 26.08, lng: 119.30 },
  { name: '湖南', value: 510, lat: 28.19, lng: 112.98 },
  { name: '安徽', value: 430, lat: 31.86, lng: 117.27 },
  { name: '河北', value: 390, lat: 38.03, lng: 114.48 },
  { name: '辽宁', value: 370, lat: 41.80, lng: 123.38 },
  { name: '陕西', value: 340, lat: 34.27, lng: 108.95 },
  { name: '重庆', value: 420, lat: 29.59, lng: 106.54 },
  { name: '云南', value: 280, lat: 25.04, lng: 102.73 },
  { name: '广西', value: 310, lat: 22.84, lng: 108.33 }
]

const mockLineData = {
  hours: ['00:00', '02:00', '04:00', '06:00', '08:00', '10:00', '12:00', '14:00', '16:00', '18:00', '20:00', '22:00'],
  visits: [120, 80, 60, 90, 320, 580, 420, 650, 720, 540, 380, 260],
  ops: [60, 40, 30, 50, 180, 340, 250, 420, 480, 360, 220, 140]
}

const mockLogPool = [
  { user: '张三', action: '登录系统', status: '成功' },
  { user: '李四', action: '修改权限', status: '成功' },
  { user: '王五', action: '导出报表', status: '成功' },
  { user: '赵六', action: '删除用户', status: '失败' },
  { user: '钱七', action: '新增角色', status: '成功' },
  { user: '孙八', action: '审批通过', status: '成功' },
  { user: '周九', action: '重置密码', status: '成功' },
  { user: '吴十', action: '上传文件', status: '失败' },
  { user: '郑一', action: '分配菜单', status: '成功' },
  { user: '冯二', action: '查看日志', status: '成功' }
]

const logList = ref([])

// ---- 创建脉冲标记图标 ----
function createPulseIcon(size, color) {
  return L.divIcon({
    className: 'pulse-marker',
    html: `<div class="pulse-dot" style="--size:${size}px; --color:${color}">
             <div class="pulse-ring"></div>
             <div class="pulse-core"></div>
           </div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2]
  })
}

// ---- 初始化 Leaflet 地图 ----
async function initMap() {
  map = L.map(mapRef.value, {
    center: [35.8, 104.5], zoom: 5,
    zoomControl: false, attributionControl: false,
    dragging: true, scrollWheelZoom: true, doubleClickZoom: false,
    touchZoom: true, keyboard: false, minZoom: 5, maxZoom: 18
  })

  const transparentTile = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVQI12NgAAIABQABNjN9GQAAAABJRUEFTkSuQmCC'

  L.tileLayer('/map/tiles/{z}/{x}/{y}.png', {
    maxZoom: 18, minZoom: 5, errorTileUrl: transparentTile
  }).addTo(map)

  L.tileLayer('http://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}', {
    subdomains: '1234', maxZoom: 18, minZoom: 9, opacity: 1
  }).addTo(map)

  mockMapPoints.forEach(point => {
    const size = Math.max(point.value / 40, 16)
    const marker = L.marker([point.lat, point.lng], {
      icon: createPulseIcon(size, point.value > 800 ? cyanColor : greenColor)
    }).addTo(map)
    marker.bindTooltip(
      `<div style="text-align:center;font-size:13px;color:#00e5ff">
        <div style="font-weight:bold;margin-bottom:2px">${point.name}</div>
        <div>访问量: <span style="color:#fff">${point.value}</span></div>
      </div>`,
      { className: 'custom-tooltip', direction: 'top', offset: [0, -size / 2] }
    )
  })

  mockMapPoints.filter(p => p.name !== '北京').forEach(point => {
    const beijing = mockMapPoints[0]
    L.polyline([[beijing.lat, beijing.lng], [point.lat, point.lng]], {
      color: cyanColor, weight: 1, opacity: 0.3, dashArray: '4 8'
    }).addTo(map)
    const movingDot = L.circleMarker([beijing.lat, beijing.lng], {
      radius: 3, color: cyanColor, fillColor: cyanColor, fillOpacity: 1, weight: 0
    }).addTo(map)
    animateDot(movingDot, [beijing.lat, beijing.lng], [point.lat, point.lng], 4000)
  })
}

function animateDot(dot, start, end, duration) {
  const startTime = performance.now()
  function step(now) {
    const progress = ((now - startTime) % duration) / duration
    dot.setLatLng([start[0] + (end[0] - start[0]) * progress, start[1] + (end[1] - start[1]) * progress])
    requestAnimationFrame(step)
  }
  requestAnimationFrame(step)
}

// ---- ECharts ----
function initLeftBar() {
  leftBarChart = echarts.init(leftBarRef.value)
  leftBarChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, backgroundColor: 'rgba(0,20,40,0.9)', borderColor: cyanColor, textStyle: { color: '#fff' } },
    grid: { left: '3%', right: '6%', bottom: '3%', top: '8%', containLabel: true },
    xAxis: { type: 'value', axisLine: { lineStyle: { color: axisLineColor } }, axisLabel: { color: textColor }, splitLine: { lineStyle: { color: 'rgba(0,228,255,0.08)' } } },
    yAxis: { type: 'category', data: mockBarData.departments, axisLine: { lineStyle: { color: axisLineColor } }, axisLabel: { color: textColor } },
    series: [{ type: 'bar', data: mockBarData.counts, barWidth: 14, itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [{ offset: 0, color: 'rgba(0,228,255,0.3)' }, { offset: 1, color: cyanColor }]) } }]
  })
}

function initLeftPie() {
  leftPieChart = echarts.init(leftPieRef.value)
  leftPieChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)', backgroundColor: 'rgba(0,20,40,0.9)', borderColor: cyanColor, textStyle: { color: '#fff' } },
    legend: { orient: 'vertical', right: '2%', top: 'center', textStyle: { color: textColor, fontSize: 12 } },
    series: [{ type: 'pie', radius: ['42%', '68%'], center: ['38%', '50%'], itemStyle: { borderColor: '#0a1a2e', borderWidth: 2 }, label: { show: false }, emphasis: { label: { show: true, fontSize: 13, fontWeight: 'bold', color: '#fff' } }, data: mockPieData, color: [cyanColor, greenColor, yellowColor, redColor, '#7c4dff'] }]
  })
}

function initRightLine() {
  rightLineChart = echarts.init(rightLineRef.value)
  rightLineChart.setOption({
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(0,20,40,0.9)', borderColor: cyanColor, textStyle: { color: '#fff' } },
    legend: { data: ['访问量', '操作量'], bottom: 0, textStyle: { color: textColor } },
    grid: { left: '3%', right: '4%', bottom: '14%', top: '8%', containLabel: true },
    xAxis: { type: 'category', data: mockLineData.hours, boundaryGap: false, axisLine: { lineStyle: { color: axisLineColor } }, axisLabel: { color: textColor } },
    yAxis: { type: 'value', axisLine: { lineStyle: { color: axisLineColor } }, axisLabel: { color: textColor }, splitLine: { lineStyle: { color: 'rgba(0,228,255,0.08)' } } },
    series: [
      { name: '访问量', type: 'line', smooth: true, data: mockLineData.visits, lineStyle: { color: cyanColor, width: 2 }, areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(0,228,255,0.3)' }, { offset: 1, color: 'rgba(0,228,255,0.02)' }]) }, itemStyle: { color: cyanColor } },
      { name: '操作量', type: 'line', smooth: true, data: mockLineData.ops, lineStyle: { color: greenColor, width: 2 }, areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(0,255,136,0.3)' }, { offset: 1, color: 'rgba(0,255,136,0.02)' }]) }, itemStyle: { color: greenColor } }
    ]
  })
}

// ---- 工具函数 ----
function animateNumber(obj, key, target, duration = 1500) {
  const start = obj[key]
  const range = target - start
  const startTime = performance.now()
  function step(now) {
    const progress = Math.min((now - startTime) / duration, 1)
    obj[key] = Math.round(start + range * (1 - Math.pow(1 - progress, 3)))
    if (progress < 1) requestAnimationFrame(step)
  }
  requestAnimationFrame(step)
}

function addLog() {
  const item = mockLogPool[Math.floor(Math.random() * mockLogPool.length)]
  const now = new Date()
  const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`
  logList.value.unshift({ ...item, time, isNew: true })
  if (logList.value.length > 12) logList.value.pop()
  setTimeout(() => { logList.value.forEach(l => l.isNew = false) }, 1000)
}

function updateTime() {
  const now = new Date()
  const week = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'][now.getDay()]
  currentTime.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')} ${week}`
}

function handleResize() {
  leftBarChart?.resize()
  leftPieChart?.resize()
  rightLineChart?.resize()
  map?.invalidateSize()
}

onMounted(async () => {
  updateTime()
  timer = setInterval(updateTime, 1000)
  await nextTick()
  initMap()
  initLeftBar()
  initLeftPie()
  initRightLine()
  animateNumber(animatedStats, 'totalUsers', 12860)
  animateNumber(animatedStats, 'onlineUsers', 342)
  animateNumber(animatedStats, 'todayVisits', 8756)
  animateNumber(animatedStats, 'totalOps', 56420)
  for (let i = 0; i < 8; i++) addLog()
  logTimer = setInterval(addLog, 3000)
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  clearInterval(timer)
  clearInterval(logTimer)
  window.removeEventListener('resize', handleResize)
  leftBarChart?.dispose()
  leftPieChart?.dispose()
  rightLineChart?.dispose()
  map?.remove()
})
</script>

<style scoped>
/* ---- 全局 ---- */
.big-screen {
  width: 100vw; height: 100vh;
  background: #060e1a;
  color: #a0cfff;
  font-family: 'Microsoft YaHei', sans-serif;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  position: relative;
}

/* ---- 地图背景 ---- */
.map-bg {
  position: absolute;
  top: 0; left: 0;
  width: 100%; height: 100%;
  z-index: 0;
}
.map-bg :deep(.leaflet-container) { background: #060e1a; }
.map-bg :deep(.custom-tooltip) {
  background: rgba(0,20,40,0.9) !important;
  border: 1px solid rgba(0,228,255,0.5) !important;
  border-radius: 0;
  padding: 6px 10px;
  box-shadow: 0 0 12px rgba(0,228,255,0.2);
}
.map-bg :deep(.custom-tooltip .leaflet-tooltip-tip) { border-top-color: rgba(0,20,40,0.9) !important; }
.map-bg :deep(.pulse-marker) { background: none !important; border: none !important; }

.pulse-dot { position: relative; width: var(--size); height: var(--size); }
.pulse-core {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--color); box-shadow: 0 0 8px var(--color);
}
.pulse-ring {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
  width: var(--size); height: var(--size); border-radius: 50%;
  border: 2px solid var(--color);
  animation: pulse-expand 2s ease-out infinite;
}
@keyframes pulse-expand {
  0% { transform: translate(-50%,-50%) scale(0.5); opacity: 1; }
  100% { transform: translate(-50%,-50%) scale(1.2); opacity: 0; }
}

/* ---- 顶部标题 ---- */
.screen-header {
  height: 90px;
  display: flex; align-items: center; justify-content: center;
  position: relative; z-index: 10;
  background: linear-gradient(180deg, rgba(6,14,26,0.97) 0%, rgba(6,14,26,0.5) 80%, transparent 100%);
  flex-shrink: 0;
  pointer-events: none;
}
.header-side {
  flex: 1; display: flex; align-items: center;
  height: 100%; padding: 0 30px;
}
.header-side.left { justify-content: flex-end; }
.header-side.right { justify-content: flex-start; gap: 8px; }
.header-wing {
  width: 16px; height: 16px;
  border: 2px solid rgba(0,228,255,0.7);
  transform: rotate(45deg);
  background: rgba(0,228,255,0.08);
  flex-shrink: 0;
  box-shadow: 0 0 8px rgba(0,228,255,0.3);
}
.header-line { flex: 1; height: 1px; position: relative; }
.header-line::before {
  content: ''; position: absolute; top: 0; width: 100%; height: 1px;
  background: linear-gradient(90deg, rgba(0,228,255,0.6), rgba(0,228,255,0.05));
}
.header-side.right .header-line::before {
  background: linear-gradient(90deg, rgba(0,228,255,0.05), rgba(0,228,255,0.6));
}
.header-line::after {
  content: ''; position: absolute; top: -1px; width: 60px; height: 3px;
  background: linear-gradient(90deg, transparent, #00e5ff, transparent);
  animation: line-flow 3s linear infinite;
}
.header-side.right .header-line::after { animation: line-flow-reverse 3s linear infinite; }
@keyframes line-flow { 0% { left: -60px; } 100% { left: 100%; } }
@keyframes line-flow-reverse { 0% { right: -60px; left: auto; } 100% { right: 100%; left: auto; } }

.toggle-all-btn {
  background: rgba(0,228,255,0.1);
  border: 1px solid rgba(0,228,255,0.4);
  color: #00e5ff; width: 28px; height: 28px;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; font-size: 14px;
  pointer-events: auto;
  transition: all 0.3s;
}
.toggle-all-btn:hover {
  background: rgba(0,228,255,0.25);
  box-shadow: 0 0 8px rgba(0,228,255,0.3);
}

.header-center {
  text-align: center; padding: 0 10px;
  cursor: pointer; pointer-events: auto; flex-shrink: 0;
}
.header-frame { position: relative; padding: 8px 50px; }
.header-frame .corner { position: absolute; width: 18px; height: 18px; }
.header-frame .corner::before, .header-frame .corner::after {
  content: ''; position: absolute; background: #00e5ff; box-shadow: 0 0 6px rgba(0,228,255,0.5);
}
.header-frame .corner::before { width: 18px; height: 2px; }
.header-frame .corner::after { width: 2px; height: 18px; }
.header-frame .corner.tl { top:0;left:0; } .header-frame .corner.tl::before { top:0;left:0; } .header-frame .corner.tl::after { top:0;left:0; }
.header-frame .corner.tr { top:0;right:0; } .header-frame .corner.tr::before { top:0;right:0; } .header-frame .corner.tr::after { top:0;right:0; }
.header-frame .corner.bl { bottom:0;left:0; } .header-frame .corner.bl::before { bottom:0;left:0; } .header-frame .corner.bl::after { bottom:0;left:0; }
.header-frame .corner.br { bottom:0;right:0; } .header-frame .corner.br::before { bottom:0;right:0; } .header-frame .corner.br::after { bottom:0;right:0; }

.header-title {
  font-size: 32px; font-weight: 700; letter-spacing: 8px;
  background: linear-gradient(180deg, #fff 0%, #00e5ff 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  margin: 0; filter: drop-shadow(0 0 12px rgba(0,228,255,0.4));
}
.header-time { font-size: 13px; color: rgba(0,228,255,0.7); margin-top: 2px; letter-spacing: 2px; }

/* ---- 主体布局（grid） ---- */
.screen-body {
  flex: 1;
  display: grid;
  grid-template-columns: 24% 1fr 24%;
  grid-template-rows: 1fr auto;
  gap: 12px;
  padding: 0 12px 12px;
  position: relative; z-index: 5;
  min-height: 0;
  pointer-events: none;
}

/* 左右列 */
.side-col {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
  pointer-events: none;
}
.left-col { grid-column: 1; grid-row: 1 / 3; }
.right-col { grid-column: 3; grid-row: 1 / 3; }

.center-area {
  grid-column: 2; grid-row: 1;
  pointer-events: none;
}

/* ---- 卡片包裹器 ---- */
.card-wrap {
  flex: 1;
  position: relative;
  min-height: 0;
  overflow: visible;
  pointer-events: none;
}

/* 卡片本体 */
.card-wrap .card {
  width: 100%;
  height: 100%;
  background: rgba(6,14,26,0.35);
  backdrop-filter: blur(6px);
  border: 1px solid rgba(0,228,255,0.2);
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  position: relative;
  pointer-events: auto;
  transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1),
              opacity 0.3s ease;
}

/* 左侧收回：卡片向左滑出 */
.left-col .card-wrap.collapsed .card {
  transform: translateX(calc(-100% - 12px));
  opacity: 0;
  pointer-events: none;
}

/* 右侧收回：卡片向右滑出 */
.right-col .card-wrap.collapsed .card {
  transform: translateX(calc(100% + 12px));
  opacity: 0;
  pointer-events: none;
}

/* ---- 统一切换按钮 ---- */
.toggle-btn {
  position: absolute;
  width: 24px; height: 48px;
  background: rgba(6,14,26,0.9);
  border: 1px solid rgba(0,228,255,0.4);
  color: #00e5ff;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; font-size: 11px;
  pointer-events: auto;
  z-index: 20;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}
.toggle-btn:hover {
  background: rgba(0,228,255,0.15);
  box-shadow: 0 0 10px rgba(0,228,255,0.3);
  color: #fff;
}

/* 左侧按钮：始终在卡片右边缘外侧中间 */
.left-col .toggle-btn {
  top: 50%;
  right: -24px;
  transform: translateY(-50%);
  border-left: none;
}
.left-col .card-wrap.collapsed .toggle-btn {
  left: 0;
  right: auto;
}

/* 右侧按钮：始终在卡片左边缘外侧中间 */
.right-col .toggle-btn {
  top: 50%;
  left: -24px;
  transform: translateY(-50%);
  border-right: none;
}
.right-col .card-wrap.collapsed .toggle-btn {
  right: 0;
  left: auto;
}

/* ---- 底部卡片 ---- */
.bottom-card {
  grid-column: 2; grid-row: 2;
  position: relative;
  height: 200px;
  pointer-events: none;
  overflow: visible;
}
.bottom-card .card {
  width: 100%;
  height: 100%;
  background: rgba(6,14,26,0.55);
  backdrop-filter: blur(6px);
  border: 1px solid rgba(0,228,255,0.2);
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  position: relative;
  pointer-events: auto;
  transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1),
              opacity 0.3s ease;
}
.bottom-card.collapsed .card {
  transform: translateY(calc(100% + 12px));
  opacity: 0;
  pointer-events: none;
}

/* 底部按钮：始终在卡片上边缘外侧中间 */
.bottom-card .toggle-btn {
  top: -24px;
  left: 50%;
  transform: translateX(-50%);
  width: 48px; height: 24px;
  border-bottom: none;
}
.bottom-card.collapsed .toggle-btn {
  bottom: 0;
  top: auto;
}

/* ---- 卡片四角装饰 ---- */
.card::before, .card::after {
  content: ''; position: absolute; width: 14px; height: 14px;
  border-color: rgba(0,228,255,0.6); border-style: solid;
}
.card::before { top: -1px; left: -1px; border-width: 2px 0 0 2px; }
.card::after { bottom: -1px; right: -1px; border-width: 0 2px 2px 0; }

.card-header {
  font-size: 13px; font-weight: 600; color: #00e5ff;
  margin-bottom: 8px;
  display: flex; align-items: center; gap: 6px;
  flex-shrink: 0;
}

.title-dot {
  width: 6px; height: 6px;
  background: #00e5ff;
  box-shadow: 0 0 6px #00e5ff;
  display: inline-block;
  clip-path: polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%);
}

.card-body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.chart-box {
  width: 100%;
  height: 100%;
}

/* ---- 数据概览 ---- */
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  height: 100%;
  align-content: center;
}
.stat-item {
  text-align: center;
  padding: 8px;
  border: 1px solid rgba(0,228,255,0.1);
  position: relative;
}
.stat-item::before, .stat-item::after {
  content: ''; position: absolute; width: 8px; height: 8px;
  border-color: rgba(0,228,255,0.4); border-style: solid;
}
.stat-item::before { top: -1px; left: -1px; border-width: 1px 0 0 1px; }
.stat-item::after { bottom: -1px; right: -1px; border-width: 0 1px 1px 0; }

.stat-num {
  font-size: 24px; font-weight: 700;
  font-family: 'DIN', 'Courier New', monospace;
}
.stat-num.cyan { color: #00e5ff; text-shadow: 0 0 10px rgba(0,228,255,0.5); }
.stat-num.green { color: #00ff88; text-shadow: 0 0 10px rgba(0,255,136,0.5); }
.stat-num.yellow { color: #ffcc00; text-shadow: 0 0 10px rgba(255,204,0,0.5); }
.stat-num.red { color: #ff4d6a; text-shadow: 0 0 10px rgba(255,77,106,0.5); }
.stat-desc { font-size: 11px; color: rgba(160,207,255,0.6); margin-top: 4px; }

/* ---- 日志列表 ---- */
.log-list { flex: 1; overflow: hidden; font-size: 12px; }
.log-row {
  display: flex; padding: 5px 4px;
  border-bottom: 1px solid rgba(0,228,255,0.06);
  transition: background 0.5s;
}
.log-row span {
  flex: 1; text-align: center;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.log-header { color: #00e5ff; font-weight: 600; border-bottom-color: rgba(0,228,255,0.2); }
.log-new { background: rgba(0,228,255,0.08); }
.status-ok { color: #00ff88; }
.status-fail { color: #ff4d6a; }
</style>
