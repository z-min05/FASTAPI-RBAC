<template>
  <div class="smart-park">
    <!-- 顶部标题栏 -->
    <header class="park-header">
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
          <h1 class="header-title">智慧园区监控平台</h1>
          <div class="header-time">{{ currentTime }}</div>
        </div>
      </div>
      <div class="header-side right">
        <div class="header-line"></div>
        <div class="header-wing"></div>
      </div>
    </header>

    <!-- 主体内容 -->
    <div class="park-body">
      <!-- 左侧：传感器监测 -->
      <div class="side-col left-col">
        <!-- 环境监测 -->
        <div class="panel">
          <div class="panel-header">
            <span class="title-dot"></span>环境监测
          </div>
          <div class="panel-body">
            <div class="sensor-grid">
              <div class="sensor-card" v-for="s in envSensors" :key="s.label">
                <div class="sensor-icon" :style="{ color: s.color }">
                  <component :is="s.icon" />
                </div>
                <div class="sensor-info">
                  <div class="sensor-value" :style="{ color: s.color }">{{ s.value }}<span class="sensor-unit">{{ s.unit }}</span></div>
                  <div class="sensor-label">{{ s.label }}</div>
                </div>
                <div class="sensor-status" :class="s.status">{{ s.statusText }}</div>
              </div>
            </div>
          </div>
        </div>
        <!-- 事件告警 -->
        <div class="panel">
          <div class="panel-header">
            <span class="title-dot"></span>事件告警
          </div>
          <div class="panel-body">
            <div class="alarm-list">
              <div class="alarm-row alarm-header"><span>时间</span><span>位置</span><span>事件</span><span>级别</span></div>
              <div v-for="(a, i) in alarmList" :key="i" class="alarm-row" :class="{ 'alarm-new': a.isNew }">
                <span>{{ a.time }}</span><span>{{ a.sensor }}</span><span>{{ a.type }}</span>
                <span :class="a.level === '严重' ? 'level-critical' : 'level-warning'">{{ a.level }}</span>
              </div>
            </div>
          </div>
        </div>
        <!-- 大门门禁统计 -->
        <div class="panel gate-panel">
          <div class="panel-header">
            <span class="title-dot"></span>大门门禁统计
          </div>
          <div class="panel-body">
            <div class="gate-stats">
              <div class="gate-stat-row">
                <div class="gate-stat-item person-in">
                  <div class="gate-icon"><UserOutlined /></div>
                  <div class="gate-info">
                    <div class="gate-num">{{ gateStats.personIn }}</div>
                    <div class="gate-label">人员进入</div>
                  </div>
                </div>
                <div class="gate-stat-item person-out">
                  <div class="gate-icon"><UserOutlined /></div>
                  <div class="gate-info">
                    <div class="gate-num">{{ gateStats.personOut }}</div>
                    <div class="gate-label">人员外出</div>
                  </div>
                </div>
                <div class="gate-stat-item car-in">
                  <div class="gate-icon"><CarOutlined /></div>
                  <div class="gate-info">
                    <div class="gate-num">{{ gateStats.carIn }}</div>
                    <div class="gate-label">车辆进入</div>
                  </div>
                </div>
                <div class="gate-stat-item car-out">
                  <div class="gate-icon"><CarOutlined /></div>
                  <div class="gate-info">
                    <div class="gate-num">{{ gateStats.carOut }}</div>
                    <div class="gate-label">车辆外出</div>
                  </div>
                </div>
              </div>
              <div class="gate-plates">
                <div class="plates-title">最近进入车牌</div>
                <div class="plates-list">
                  <span class="plate-tag" v-for="(p, i) in recentPlates" :key="i">{{ p.plate }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 中间区域 -->
      <div class="center-col">
        <!-- 3D 园区展示 -->
        <div class="three-d-area">
          <div ref="threeRef" class="three-container"></div>
          <!-- 日照调试滑块 -->
          <div class="daylight-debug">
            <label>日照模拟</label>
            <input type="range" min="0" max="24" step="0.1" v-model.number="debugHour" @input="onDebugHourChange" />
            <span class="debug-time">{{ formatDebugHour(debugHour) }}</span>
            <button class="debug-reset" @click="debugHour = null; updateDaylight()">恢复实时</button>
          </div>
        </div>
        <!-- 底部摄像头画面 -->
        <div class="camera-bar">
          <div
            class="camera-item"
            v-for="cam in cameraList"
            :key="cam.id"
            :class="{ active: enlargedCamera?.id === cam.id }"
            @click="openCameraModal(cam)"
          >
            <div class="camera-feed">
              <div class="camera-placeholder">
                <VideoCameraOutlined style="font-size: 28px; opacity: 0.4" />
                <span>{{ cam.name }}</span>
              </div>
            </div>
            <div class="camera-label">
              <span class="cam-dot" :class="{ online: cam.is_online }"></span>
              {{ cam.name }}
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：控制面板 -->
      <div class="side-col right-col">
        <!-- 设备总览 -->
        <div class="panel">
          <div class="panel-header">
            <span class="title-dot"></span>设备总览
          </div>
          <div class="panel-body">
            <div class="overview-grid">
              <div class="overview-item" v-for="o in deviceOverview" :key="o.label">
                <div class="overview-num" :style="{ color: o.color }">{{ o.value }}</div>
                <div class="overview-label">{{ o.label }}</div>
              </div>
            </div>
          </div>
        </div>
        <!-- 停车位列表 -->
        <div class="panel parking-panel">
          <div class="panel-header">
            <span class="title-dot"></span>停车位状态
            <span class="parking-summary">{{ parkingUsed }}/{{ parkingTotal }} 已占用</span>
          </div>
          <div class="panel-body">
            <div class="parking-lot">
              <div
                class="parking-spot"
                v-for="spot in parkingList"
                :key="spot.id"
                :class="{ occupied: spot.occupied, highlighted: selectedParkingId === spot.id }"
                @click="highlightParkingSpot(selectedParkingId === spot.id ? null : spot.id)"
              >
                <div class="spot-icon">
                  <CarOutlined v-if="spot.occupied" />
                  <span v-else class="spot-empty">P</span>
                </div>
                <div class="spot-info">
                  <div class="spot-id">{{ spot.id }}</div>
                  <div class="spot-status" :class="spot.occupied ? 'busy' : 'free'">
                    {{ spot.occupied ? spot.plate : '空闲' }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <!-- 设备状态 -->
        <div class="panel device-panel">
          <div class="panel-header">
            <span class="title-dot"></span>设备状态
          </div>
          <div class="panel-body">
            <div class="device-tabs">
              <button
                v-for="t in deviceTabs"
                :key="t.key"
                :class="{ active: activeDeviceTab === t.key }"
                @click="activeDeviceTab = t.key"
              >{{ t.label }}</button>
            </div>
            <div class="device-grid">
              <div class="device-item" v-for="d in filteredDevices" :key="d.id">
                <div class="device-info">
                  <div class="device-id">{{ d.id }}</div>
                  <div class="device-loc">{{ d.location }}</div>
                </div>
                <span class="device-state" :class="d.on ? 'on' : 'off'">{{ d.on ? '运行' : '关闭' }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 摄像头放大弹窗 -->
    <div class="camera-modal" v-if="enlargedCamera" @click.self="closeCameraModal">
      <div class="modal-content">
        <div class="modal-header">
          <span>{{ enlargedCamera.name }} - 实时画面</span>
          <CloseOutlined class="modal-close" @click="closeCameraModal" />
        </div>
        <div class="modal-body">
          <video ref="modalVideoRef" class="modal-video" muted v-show="modalStreamRunning"></video>
          <div class="camera-placeholder large" v-if="!modalStreamRunning">
            <VideoCameraOutlined style="font-size: 64px; opacity: 0.3" />
            <span>正在连接视频流...</span>
          </div>
        </div>
        <div class="modal-footer">
          <button class="stream-btn" @click="startModalStream" v-if="!modalStreamRunning">
            <VideoCameraOutlined /> 启动视频流
          </button>
          <button class="stream-btn stop" @click="stopModalStream" v-else>
            <VideoCameraOutlined /> 停止视频流
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import {
  CloseOutlined,
  VideoCameraOutlined,
  DashboardOutlined,
  CloudOutlined,
  BulbOutlined,
  EnvironmentOutlined,
  FireOutlined,
  SoundOutlined,
  CarOutlined,
  UserOutlined
} from '@ant-design/icons-vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import flvjs from 'flv.js/dist/flv.min.js'
import {
  getCameras, startStream, stopStream, connectCamera
} from '@/api/camera'

const threeRef = ref(null)
const currentTime = ref('')
const enlargedCamera = ref(null)
const modalVideoRef = ref(null)
const modalStreamRunning = ref(false)
let modalFlvPlayer = null
let modalRetryCount = 0
const MAX_RETRY = 3
const debugHour = ref(null) // null = 使用实时时间，数字 = 调试时间
const selectedParkingId = ref(null) // 当前高亮的停车位ID

let threeRenderer = null
let threeScene = null
let threeCamera = null
let threeControls = null
let animFrameId = null
let timer = null
let alarmTimer = null

// ---- 环境传感器 ----
const envSensors = reactive([
  { label: '温度', value: 26.3, unit: '°C', icon: FireOutlined, color: '#4facfe', status: 'normal', statusText: '正常' },
  { label: '湿度', value: 58.2, unit: '%', icon: CloudOutlined, color: '#00e5ff', status: 'normal', statusText: '正常' },
  { label: 'PM2.5', value: 35, unit: 'μg/m³', icon: EnvironmentOutlined, color: '#00ff88', status: 'normal', statusText: '优' },
  { label: '噪音', value: 42, unit: 'dB', icon: SoundOutlined, color: '#7c4dff', status: 'normal', statusText: '正常' },
  { label: '风速', value: 3.2, unit: 'm/s', icon: DashboardOutlined, color: '#ffcc00', status: 'normal', statusText: '正常' },
  { label: '光照', value: 860, unit: 'Lux', icon: BulbOutlined, color: '#ff9100', status: 'normal', statusText: '正常' }
])

// ---- 事件告警列表 ----
const alarmList = ref([])
const alarmPool = [
  { sensor: 'A栋3层', type: '火灾报警', level: '严重' },
  { sensor: 'B栋大门', type: '非法闯入', level: '严重' },
  { sensor: 'C区围栏', type: '翻越围栏', level: '严重' },
  { sensor: 'D区仓库', type: '烟雾报警', level: '严重' },
  { sensor: 'A栋1层', type: '门禁异常', level: '警告' },
  { sensor: 'B区车库', type: '车辆违停', level: '警告' },
  { sensor: 'E区机房', type: '温度过高', level: '警告' },
  { sensor: 'F区走廊', type: '人员滞留', level: '警告' }
]

function addAlarm() {
  const item = alarmPool[Math.floor(Math.random() * alarmPool.length)]
  const now = new Date()
  const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`
  alarmList.value.unshift({ ...item, time, isNew: true })
  if (alarmList.value.length > 10) alarmList.value.pop()
  setTimeout(() => alarmList.value.forEach(a => a.isNew = false), 1000)
}

// ---- 园区3D标签（位置对应3D场景坐标）----
const parkTags = [
  { name: 'A栋办公楼', x: -8, y: 9, z: -5, status: 'normal' },
  { name: 'B栋研发楼', x: 4, y: 11, z: -6, status: 'normal' },
  { name: 'C栋数据中心', x: 12, y: 7, z: -3, status: 'warning' },
  { name: '地下车库', x: -6, y: 4, z: 6, status: 'normal' },
  { name: '综合楼', x: 6, y: 5, z: 7, status: 'normal' }
]

// ---- 摄像头列表 ----
const cameraList = ref([])

async function loadCameras() {
  try {
    const res = await getCameras({ page: 1, page_size: 100 })
    cameraList.value = res.data.items || []
  } catch (e) {
    console.error('加载摄像头列表失败:', e)
  }
}

async function openCameraModal(cam) {
  enlargedCamera.value = cam
  modalStreamRunning.value = false
  modalRetryCount = 0
  await nextTick()
  await startModalStream()
}

async function startModalStream() {
  if (!enlargedCamera.value) return
  const cam = enlargedCamera.value
  try {
    if (!cam.is_online) {
      await connectCamera(cam.id)
    }
    await startStream(cam.id)
    // FLV端点会在服务端等待数据就绪，前端直接连接即可
    if (flvjs && flvjs.isSupported() && modalVideoRef.value) {
      destroyModalFlvPlayer()
      const token = localStorage.getItem('access_token')
      modalFlvPlayer = flvjs.createPlayer({
        type: 'flv',
        url: `/api/v1/cameras/${cam.id}/stream/live.flv`,
        isLive: true,
        hasAudio: false,
        hasVideo: true,
        cors: true,
      }, {
        enableStashBuffer: true,
        stashInitialSize: 1024,
        autoCleanupSourceBuffer: true,
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
      })
      // 监听flv.js错误
      modalFlvPlayer.on(flvjs.Events.ERROR, (errorType, errorDetail) => {
        console.warn('flv.js播放错误:', errorType, errorDetail)
        if (errorDetail === flvjs.ErrorDetails.FORMAT_UNSUPPORTED) {
          destroyModalFlvPlayer()
          modalRetryCount++
          if (modalRetryCount < MAX_RETRY) {
            console.log(`FLV格式错误，第${modalRetryCount}次重试...`)
            setTimeout(() => {
              if (enlargedCamera.value?.id === cam.id) {
                startModalStream()
              }
            }, 2000)
          } else {
            console.error('FLV流重试次数已用尽，请检查摄像头RTSP流是否正常')
            modalStreamRunning.value = false
          }
        }
      })
      modalFlvPlayer.attachMediaElement(modalVideoRef.value)
      modalFlvPlayer.load()
      modalFlvPlayer.play().catch(() => {})
      modalStreamRunning.value = true
    }
  } catch (e) {
    console.error('启动视频流失败:', e)
  }
}

async function stopModalStream() {
  if (!enlargedCamera.value) return
  try {
    destroyModalFlvPlayer()
    await stopStream(enlargedCamera.value.id)
    modalStreamRunning.value = false
  } catch (e) {
    console.error('停止视频流失败:', e)
  }
}

function destroyModalFlvPlayer() {
  if (modalFlvPlayer) {
    try {
      modalFlvPlayer.pause()
      modalFlvPlayer.unload()
      modalFlvPlayer.detachMediaElement()
      modalFlvPlayer.destroy()
    } catch (e) {}
    modalFlvPlayer = null
  }
}

function closeCameraModal() {
  stopModalStream()
  enlargedCamera.value = null
}

// ---- 设备总览 ----
const deviceOverview = computed(() => [
  { label: '空调', value: deviceList.value.filter(d => d.type === 'ac').length, color: '#4facfe' },
  { label: '灯具', value: deviceList.value.filter(d => d.type === 'light').length, color: '#ffcc00' },
  { label: '门禁', value: deviceList.value.filter(d => d.type === 'door').length, color: '#00e5ff' },
  { label: '在线率', value: deviceOnlineRate.value, color: '#00ff88' }
])

// ---- 设备状态 ----
const deviceList = ref([
  // 空调
  { id: 'AC-A01', type: 'ac', location: 'A栋3层', on: true },
  { id: 'AC-A02', type: 'ac', location: 'A栋5层', on: true },
  { id: 'AC-B01', type: 'ac', location: 'B栋2层', on: false },
  { id: 'AC-B02', type: 'ac', location: 'B栋4层', on: true },
  { id: 'AC-C01', type: 'ac', location: 'C栋机房', on: true },
  { id: 'AC-D01', type: 'ac', location: '地下车库', on: false },
  // 灯具
  { id: 'LT-A01', type: 'light', location: 'A栋走廊', on: true },
  { id: 'LT-A02', type: 'light', location: 'A栋大厅', on: true },
  { id: 'LT-B01', type: 'light', location: 'B栋走廊', on: true },
  { id: 'LT-B02', type: 'light', location: 'B栋会议室', on: false },
  { id: 'LT-C01', type: 'light', location: '园区路灯', on: true },
  { id: 'LT-D01', type: 'light', location: '地下车库', on: true },
  // 门禁
  { id: 'DR-A01', type: 'door', location: 'A栋正门', on: true },
  { id: 'DR-B01', type: 'door', location: 'B栋正门', on: true },
  { id: 'DR-C01', type: 'door', location: 'C栋机房', on: true },
  { id: 'DR-G01', type: 'door', location: '园区大门', on: true },
])

const deviceOnlineRate = computed(() => {
  const total = deviceList.value.length
  const online = deviceList.value.filter(d => d.on).length
  return total > 0 ? Math.round(online / total * 100) + '%' : '0%'
})

const deviceTabs = [
  { key: 'all', label: '全部' },
  { key: 'ac', label: '空调' },
  { key: 'light', label: '灯具' },
  { key: 'door', label: '门禁' }
]
const activeDeviceTab = ref('all')
const filteredDevices = computed(() => {
  if (activeDeviceTab.value === 'all') return deviceList.value
  return deviceList.value.filter(d => d.type === activeDeviceTab.value)
})

// ---- 大门门禁统计 ----
const gateStats = reactive({
  personIn: 286,
  personOut: 203,
  carIn: 47,
  carOut: 35
})

const recentPlates = ref([
  { plate: '京A·88888', time: '20:45' },
  { plate: '京B·66666', time: '20:32' },
  { plate: '京C·12345', time: '20:18' },
  { plate: '京D·77777', time: '20:05' },
  { plate: '京E·99999', time: '19:50' },
  { plate: '京F·55555', time: '19:36' }
])

const platePool = ['京A','京B','京C','京D','京E','京F','京G','京H','京J','京K']
function generatePlate() {
  const prefix = platePool[Math.floor(Math.random() * platePool.length)]
  const num = String(Math.floor(Math.random() * 90000) + 10000)
  return `${prefix}·${num}`
}

function updateGateStats() {
  // 随机增加进出记录
  if (Math.random() > 0.5) {
    gateStats.personIn += Math.floor(Math.random() * 3) + 1
  } else {
    gateStats.personOut += Math.floor(Math.random() * 3) + 1
  }
  if (Math.random() > 0.7) {
    const plate = generatePlate()
    const now = new Date()
    const time = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`
    gateStats.carIn += 1
    recentPlates.value.unshift({ plate, time })
    if (recentPlates.value.length > 8) recentPlates.value.pop()
  }
  if (Math.random() > 0.8) {
    gateStats.carOut += 1
  }
}

// ---- 停车位数据 ----
const parkingList = reactive([
  { id: 'A-01', occupied: true, plate: '京A·88888' },
  { id: 'A-02', occupied: false, plate: '' },
  { id: 'A-03', occupied: true, plate: '京B·66666' },
  { id: 'A-04', occupied: true, plate: '京C·12345' },
  { id: 'A-05', occupied: false, plate: '' },
  { id: 'B-01', occupied: true, plate: '京D·77777' },
  { id: 'B-02', occupied: false, plate: '' },
  { id: 'B-03', occupied: false, plate: '' },
  { id: 'B-04', occupied: true, plate: '京E·99999' },
  { id: 'B-05', occupied: true, plate: '京F·55555' },
  { id: 'C-01', occupied: false, plate: '' },
  { id: 'C-02', occupied: true, plate: '京G·33333' },
  { id: 'C-03', occupied: true, plate: '京H·11111' },
  { id: 'C-04', occupied: false, plate: '' },
  { id: 'C-05', occupied: true, plate: '京J·22222' },
  { id: 'D-01', occupied: false, plate: '' },
  { id: 'D-02', occupied: true, plate: '京K·44444' },
  { id: 'D-03', occupied: false, plate: '' },
  { id: 'D-04', occupied: true, plate: '京L·10101' },
  { id: 'D-05', occupied: false, plate: '' },
])

const parkingTotal = computed(() => parkingList.length)
const parkingUsed = computed(() => parkingList.filter(s => s.occupied).length)
const parkingRate = computed(() => {
  if (parkingTotal.value === 0) return '0%'
  return Math.round(parkingUsed.value / parkingTotal.value * 100) + '%'
})

// ---- 日照模拟系统 ----
// 根据小时(0-24浮点)计算日照参数
function getDaylightParams(hour) {
  // 日出5:30 日落18:30
  const sunrise = 5.5, sunset = 18.5
  let sunAltitude = 0 // 太阳高度角 0~1
  let ambientIntensity = 0.08
  let dirIntensity = 0
  let ambientColor = [0x0a, 0x16, 0x28] // 深蓝夜色
  let dirColor = [0xff, 0xff, 0xff]
  let skyColor = [0x0a, 0x16, 0x28]
  let fogColor = [0x0a, 0x16, 0x28]
  let windowOpacity = 0.35 // 夜间窗户亮
  let groundColor = [0x0d, 0x1f, 0x3c]

  if (hour >= sunrise && hour <= sunset) {
    // 白天：计算太阳高度
    const progress = (hour - sunrise) / (sunset - sunrise) // 0~1
    sunAltitude = Math.sin(progress * Math.PI) // 正弦曲线，正午最高

    // 环境光：白天从弱到强再到弱
    ambientIntensity = 0.15 + sunAltitude * 0.65

    // 方向光强度
    dirIntensity = 0.2 + sunAltitude * 1.0

    // 天空颜色渐变
    if (progress < 0.15) {
      // 日出：橙红 → 蓝
      const t = progress / 0.15
      skyColor = lerpColor([0x1a, 0x0a, 0x2e], [0x4a, 0x7a, 0xc4], t)
      ambientColor = lerpColor([0x1a, 0x0a, 0x2e], [0x5a, 0x8a, 0xc4], t)
      dirColor = lerpColor([0xff, 0x88, 0x33], [0xff, 0xee, 0xcc], t)
      fogColor = lerpColor([0x1a, 0x0a, 0x2e], [0x5a, 0x8a, 0xc4], t)
    } else if (progress > 0.85) {
      // 日落：蓝 → 橙红
      const t = (progress - 0.85) / 0.15
      skyColor = lerpColor([0x4a, 0x7a, 0xc4], [0x2a, 0x10, 0x20], t)
      ambientColor = lerpColor([0x5a, 0x8a, 0xc4], [0x2a, 0x10, 0x20], t)
      dirColor = lerpColor([0xff, 0xee, 0xcc], [0xff, 0x66, 0x22], t)
      fogColor = lerpColor([0x5a, 0x8a, 0xc4], [0x2a, 0x10, 0x20], t)
    } else {
      // 正午：明亮蓝天
      skyColor = [0x4a, 0x7a, 0xc4]
      ambientColor = [0x6a, 0x9a, 0xd4]
      dirColor = [0xff, 0xff, 0xf0]
      fogColor = [0x6a, 0x9a, 0xd4]
    }

    // 地面颜色：白天变亮
    groundColor = lerpColor([0x0d, 0x1f, 0x3c], [0x3a, 0x5a, 0x4a], sunAltitude)

    // 白天窗户不发光
    windowOpacity = Math.max(0.02, 0.35 - sunAltitude * 0.5)

  } else {
    // 夜间
    const nightProgress = hour < sunrise
      ? (hour + 24 - sunset) / (24 - sunset + sunrise)
      : (hour - sunset) / (24 - sunset + sunrise)
    // 深夜更暗
    const nightDepth = 1 - Math.sin(nightProgress * Math.PI) * 0.3
    ambientIntensity = 0.06 + (1 - nightDepth) * 0.04
    dirIntensity = 0.05
    windowOpacity = 0.3 + (1 - nightDepth) * 0.1
  }

  // 太阳方向（东升西落）
  let sunAngle = 0
  if (hour >= sunrise && hour <= sunset) {
    sunAngle = ((hour - sunrise) / (sunset - sunrise)) * Math.PI
  }

  return {
    sunAltitude, sunAngle,
    ambientIntensity, dirIntensity,
    ambientColor, dirColor,
    skyColor, fogColor, groundColor,
    windowOpacity
  }
}

function lerpColor(a, b, t) {
  return a.map((v, i) => Math.round(v + (b[i] - v) * t))
}

function rgbToHex(r, g, b) {
  return (r << 16) | (g << 8) | b
}

// 存储需要动态更新的材质引用
let dirLightRef = null
let ambientLightRef = null
let windowMeshes = []
let groundMeshRef = null
let parkingSpotMeshes = {} // { spotId: { spot, car, label } }

// ---- 创建3D车辆模型 ----
function createCarMesh() {
  const group = new THREE.Group()
  const bodyMat = new THREE.MeshStandardMaterial({ color: 0x3a5a8a, roughness: 0.4, metalness: 0.6 })
  const roofMat = new THREE.MeshStandardMaterial({ color: 0x2a4a7a, roughness: 0.4, metalness: 0.5 })
  const glassMat = new THREE.MeshBasicMaterial({ color: 0x4facfe, transparent: true, opacity: 0.3 })
  const wheelMat = new THREE.MeshStandardMaterial({ color: 0x1a1a1a, roughness: 0.8 })

  // 车身底盘
  const bodyGeo = new THREE.BoxGeometry(1.8, 0.5, 3.6)
  const body = new THREE.Mesh(bodyGeo, bodyMat)
  body.position.y = 0.45
  body.castShadow = true
  group.add(body)

  // 车顶
  const roofGeo = new THREE.BoxGeometry(1.6, 0.45, 1.8)
  const roof = new THREE.Mesh(roofGeo, roofMat)
  roof.position.set(0, 0.92, -0.2)
  roof.castShadow = true
  group.add(roof)

  // 前挡风玻璃
  const frontGlassGeo = new THREE.PlaneGeometry(1.5, 0.4)
  const frontGlass = new THREE.Mesh(frontGlassGeo, glassMat)
  frontGlass.position.set(0, 0.9, 0.7)
  frontGlass.rotation.x = -0.3
  group.add(frontGlass)

  // 后挡风玻璃
  const rearGlass = new THREE.Mesh(frontGlassGeo, glassMat)
  rearGlass.position.set(0, 0.9, -1.1)
  rearGlass.rotation.x = 0.3
  group.add(rearGlass)

  // 车轮
  const wheelGeo = new THREE.CylinderGeometry(0.25, 0.25, 0.15, 8)
  const wheelPositions = [
    [-0.9, 0.25, 1.1], [0.9, 0.25, 1.1],
    [-0.9, 0.25, -1.1], [0.9, 0.25, -1.1]
  ]
  wheelPositions.forEach(([wx, wy, wz]) => {
    const wheel = new THREE.Mesh(wheelGeo, wheelMat)
    wheel.position.set(wx, wy, wz)
    wheel.rotation.z = Math.PI / 2
    group.add(wheel)
  })

  // 车灯
  const headlightGeo = new THREE.BoxGeometry(0.3, 0.15, 0.05)
  const headlightMat = new THREE.MeshBasicMaterial({ color: 0xffeeaa })
  const hl1 = new THREE.Mesh(headlightGeo, headlightMat)
  hl1.position.set(-0.6, 0.5, 1.81)
  group.add(hl1)
  const hl2 = new THREE.Mesh(headlightGeo, headlightMat)
  hl2.position.set(0.6, 0.5, 1.81)
  group.add(hl2)

  // 尾灯
  const taillightMat = new THREE.MeshBasicMaterial({ color: 0xff3333 })
  const tl1 = new THREE.Mesh(headlightGeo, taillightMat)
  tl1.position.set(-0.6, 0.5, -1.81)
  group.add(tl1)
  const tl2 = new THREE.Mesh(headlightGeo, taillightMat)
  tl2.position.set(0.6, 0.5, -1.81)
  group.add(tl2)

  return group
}

// ---- 高亮停车位 ----
const initialCameraPos = { x: 35, y: 28, z: 35 }
const initialCameraTarget = { x: 0, y: 0, z: 0 }

function highlightParkingSpot(spotId) {
  // 先清除所有高亮
  Object.entries(parkingSpotMeshes).forEach(([id, meshes]) => {
    const isOccupied = parkingList.find(s => s.id === id)?.occupied
    const normalColor = isOccupied ? 0xff4d6a : 0x00ff88
    meshes.spot.material.opacity = 0.15
    meshes.spot.material.color.setHex(normalColor)
    meshes.edge.material.color.setHex(normalColor)
    meshes.edge.material.opacity = 0.5
  })

  if (!spotId || !parkingSpotMeshes[spotId]) {
    selectedParkingId.value = null
    // 回到初始视角
    flyCameraTo(initialCameraPos, initialCameraTarget)
    return
  }

  selectedParkingId.value = spotId
  const meshes = parkingSpotMeshes[spotId]
  // 高亮效果
  meshes.spot.material.opacity = 0.5
  meshes.spot.material.color.setHex(0xffff00)
  meshes.edge.material.color.setHex(0xffff00)
  meshes.edge.material.opacity = 1.0

  // 相机飞向该停车位
  flyCameraTo(
    { x: meshes.sx + 8, y: 12, z: meshes.sz + 8 },
    { x: meshes.sx, y: 0, z: meshes.sz }
  )
}

function flyCameraTo(toPos, toTarget, duration = 800) {
  if (!threeCamera || !threeControls) return
  const fromPos = { x: threeCamera.position.x, y: threeCamera.position.y, z: threeCamera.position.z }
  const fromTarget = { x: threeControls.target.x, y: threeControls.target.y, z: threeControls.target.z }
  const start = performance.now()

  function flyAnimation(now) {
    const elapsed = now - start
    const t = Math.min(elapsed / duration, 1)
    const ease = t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t
    threeCamera.position.set(
      fromPos.x + (toPos.x - fromPos.x) * ease,
      fromPos.y + (toPos.y - fromPos.y) * ease,
      fromPos.z + (toPos.z - fromPos.z) * ease
    )
    threeControls.target.set(
      fromTarget.x + (toTarget.x - fromTarget.x) * ease,
      fromTarget.y + (toTarget.y - fromTarget.y) * ease,
      fromTarget.z + (toTarget.z - fromTarget.z) * ease
    )
    threeControls.update()
    if (t < 1) requestAnimationFrame(flyAnimation)
  }
  requestAnimationFrame(flyAnimation)
}

// ---- 3D 园区 ----
function initThree() {
  const container = threeRef.value
  const w = container.clientWidth
  const h = container.clientHeight

  threeScene = new THREE.Scene()
  threeScene.background = new THREE.Color(0x0a1628)
  threeScene.fog = new THREE.Fog(0x0a1628, 40, 120)

  threeCamera = new THREE.PerspectiveCamera(45, w / h, 0.1, 300)
  threeCamera.position.set(35, 28, 35)
  threeCamera.lookAt(0, 0, 0)

  threeRenderer = new THREE.WebGLRenderer({ antialias: true })
  threeRenderer.setSize(w, h)
  threeRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  threeRenderer.shadowMap.enabled = true
  container.appendChild(threeRenderer.domElement)

  threeControls = new OrbitControls(threeCamera, threeRenderer.domElement)
  threeControls.enableDamping = true
  threeControls.dampingFactor = 0.05
  threeControls.maxPolarAngle = Math.PI / 2.2
  threeControls.minDistance = 15
  threeControls.maxDistance = 90

  // 灯光
  ambientLightRef = new THREE.AmbientLight(0x4facfe, 0.4)
  threeScene.add(ambientLightRef)
  dirLightRef = new THREE.DirectionalLight(0xffffff, 0.8)
  dirLightRef.position.set(15, 25, 15)
  dirLightRef.castShadow = true
  threeScene.add(dirLightRef)
  const pointLight = new THREE.PointLight(0x4facfe, 0.6, 50)
  pointLight.position.set(0, 10, 0)
  threeScene.add(pointLight)

  // 地面
  const groundGeo = new THREE.PlaneGeometry(90, 90)
  const groundMat = new THREE.MeshStandardMaterial({ color: 0x0d1f3c, roughness: 0.9 })
  const ground = new THREE.Mesh(groundGeo, groundMat)
  ground.rotation.x = -Math.PI / 2
  ground.receiveShadow = true
  groundMeshRef = ground
  threeScene.add(ground)

  // 网格线
  const gridHelper = new THREE.GridHelper(90, 45, 0x1a3a5c, 0x0d2240)
  threeScene.add(gridHelper)

  // 建筑物
  windowMeshes = []
  const buildings = [
    { x: -8, z: -5, w: 6, h: 8, d: 5, color: 0x1a3a6c, roofColor: 0x0d2240 },
    { x: 4, z: -6, w: 5, h: 10, d: 4, color: 0x1a3a6c, roofColor: 0x0d2240 },
    { x: 12, z: -3, w: 4, h: 6, d: 4, color: 0x1a3a6c, roofColor: 0x0d2240 },
    { x: -6, z: 6, w: 8, h: 3, d: 6, color: 0x152e55, roofColor: 0x0a1a30 },
    { x: 6, z: 7, w: 5, h: 4, d: 5, color: 0x152e55, roofColor: 0x0a1a30 }
  ]
  buildings.forEach(b => {
    const geo = new THREE.BoxGeometry(b.w, b.h, b.d)
    const mat = new THREE.MeshStandardMaterial({ color: b.color, roughness: 0.5, metalness: 0.3 })
    const mesh = new THREE.Mesh(geo, mat)
    mesh.position.set(b.x, b.h / 2, b.z)
    mesh.castShadow = true
    mesh.receiveShadow = true
    threeScene.add(mesh)

    // 建筑顶部发光边框
    const edgeGeo = new THREE.EdgesGeometry(geo)
    const edgeMat = new THREE.LineBasicMaterial({ color: 0x4facfe, transparent: true, opacity: 0.4 })
    const edges = new THREE.LineSegments(edgeGeo, edgeMat)
    edges.position.copy(mesh.position)
    threeScene.add(edges)

    // 屋顶
    const roofGeo = new THREE.BoxGeometry(b.w + 0.4, 0.3, b.d + 0.4)
    const roofMat = new THREE.MeshStandardMaterial({ color: b.roofColor, roughness: 0.6, metalness: 0.2 })
    const roof = new THREE.Mesh(roofGeo, roofMat)
    roof.position.set(b.x, b.h + 0.15, b.z)
    roof.castShadow = true
    threeScene.add(roof)
    // 屋顶边框
    const roofEdge = new THREE.LineSegments(
      new THREE.EdgesGeometry(roofGeo),
      new THREE.LineBasicMaterial({ color: 0x4facfe, transparent: true, opacity: 0.3 })
    )
    roofEdge.position.copy(roof.position)
    threeScene.add(roofEdge)

    // 屋顶设备（空调外机/天线）
    if (b.h >= 6) {
      const acGeo = new THREE.BoxGeometry(0.8, 0.5, 0.6)
      const acMat = new THREE.MeshStandardMaterial({ color: 0x2a3a5a, roughness: 0.7 })
      const ac1 = new THREE.Mesh(acGeo, acMat)
      ac1.position.set(b.x - b.w * 0.25, b.h + 0.55, b.z - b.d * 0.2)
      threeScene.add(ac1)
      const ac2 = new THREE.Mesh(acGeo, acMat)
      ac2.position.set(b.x + b.w * 0.25, b.h + 0.55, b.z - b.d * 0.2)
      threeScene.add(ac2)
    }
    // 天线
    if (b.h >= 8) {
      const antennaGeo = new THREE.CylinderGeometry(0.03, 0.03, 2, 4)
      const antennaMat = new THREE.MeshStandardMaterial({ color: 0x888888, metalness: 0.8 })
      const antenna = new THREE.Mesh(antennaGeo, antennaMat)
      antenna.position.set(b.x + b.w * 0.3, b.h + 1.3, b.z + b.d * 0.3)
      threeScene.add(antenna)
      // 天线顶部红灯
      const lightGeo = new THREE.SphereGeometry(0.08, 6, 4)
      const lightMat = new THREE.MeshBasicMaterial({ color: 0xff3333 })
      const light = new THREE.Mesh(lightGeo, lightMat)
      light.position.set(b.x + b.w * 0.3, b.h + 2.3, b.z + b.d * 0.3)
      threeScene.add(light)
    }

    // 窗户发光效果 - 四面，带窗框
    const sides = [
      { pos: [b.x, b.h / 2, b.z + b.d / 2 + 0.01], rot: [0, 0, 0], w: b.w, h: b.h },
      { pos: [b.x, b.h / 2, b.z - b.d / 2 - 0.01], rot: [0, Math.PI, 0], w: b.w, h: b.h },
      { pos: [b.x + b.w / 2 + 0.01, b.h / 2, b.z], rot: [0, Math.PI / 2, 0], w: b.d, h: b.h },
      { pos: [b.x - b.w / 2 - 0.01, b.h / 2, b.z], rot: [0, -Math.PI / 2, 0], w: b.d, h: b.h }
    ]
    sides.forEach(s => {
      // 窗户网格（多行多列小窗）
      const cols = Math.max(2, Math.floor(s.w * 1.2))
      const rows = Math.max(2, Math.floor(s.h * 0.8))
      const winW = (s.w * 0.8) / cols
      const winH = (s.h * 0.6) / rows
      const startX = -(cols * winW) / 2 + winW / 2
      const startY = -(rows * winH) / 2 + winH / 2

      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const winGeo = new THREE.PlaneGeometry(winW * 0.75, winH * 0.7)
          const winMat = new THREE.MeshBasicMaterial({ color: 0x4facfe, transparent: true, opacity: 0.08 })
          const win = new THREE.Mesh(winGeo, winMat)
          const offsetX = startX + c * winW
          const offsetY = startY + r * winH
          // 相对于面中心偏移
          if (s.rot[1] === 0) {
            win.position.set(b.x + offsetX, b.h / 2 + offsetY, s.pos[2])
          } else if (s.rot[1] === Math.PI) {
            win.position.set(b.x - offsetX, b.h / 2 + offsetY, s.pos[2])
          } else if (s.rot[1] === Math.PI / 2) {
            win.position.set(s.pos[0], b.h / 2 + offsetY, b.z + offsetX)
          } else {
            win.position.set(s.pos[0], b.h / 2 + offsetY, b.z - offsetX)
          }
          win.rotation.set(...s.rot)
          threeScene.add(win)
          windowMeshes.push(win)
        }
      }
    })

    // 入口雨棚
    const canopyGeo = new THREE.BoxGeometry(b.w * 0.4, 0.08, 1.2)
    const canopyMat = new THREE.MeshStandardMaterial({ color: 0x2a4a7a, roughness: 0.4, metalness: 0.5 })
    const canopy = new THREE.Mesh(canopyGeo, canopyMat)
    canopy.position.set(b.x, 2.5, b.z + b.d / 2 + 0.6)
    threeScene.add(canopy)
    // 雨棚支柱
    const pillarGeo = new THREE.CylinderGeometry(0.06, 0.06, 2.5, 6)
    const pillarMat = new THREE.MeshStandardMaterial({ color: 0x555555, metalness: 0.7 })
    const p1 = new THREE.Mesh(pillarGeo, pillarMat)
    p1.position.set(b.x - b.w * 0.15, 1.25, b.z + b.d / 2 + 1.1)
    threeScene.add(p1)
    const p2 = new THREE.Mesh(pillarGeo, pillarMat)
    p2.position.set(b.x + b.w * 0.15, 1.25, b.z + b.d / 2 + 1.1)
    threeScene.add(p2)
  })

  // 围栏
  const fenceColor = 0x3a5a8a
  const fenceMat = new THREE.MeshStandardMaterial({ color: fenceColor, roughness: 0.6, metalness: 0.4 })
  const fenceTopMat = new THREE.MeshStandardMaterial({ color: 0x4facfe, roughness: 0.4, metalness: 0.6 })
  // 围栏范围
  const fMinX = -28, fMaxX = 28, fMinZ = -22, fMaxZ = 22
  const fenceH = 1.8
  const postSpacing = 3

  // 创建围栏段（带栅栏条）
  function createFenceSegment(x1, z1, x2, z2) {
    const dx = x2 - x1, dz = z2 - z1
    const len = Math.sqrt(dx * dx + dz * dz)
    const angle = Math.atan2(dx, dz)
    const posts = Math.floor(len / postSpacing)

    for (let i = 0; i <= posts; i++) {
      const t = i / posts
      const px = x1 + dx * t, pz = z1 + dz * t
      // 立柱
      const postGeo = new THREE.BoxGeometry(0.15, fenceH + 0.3, 0.15)
      const post = new THREE.Mesh(postGeo, fenceMat)
      post.position.set(px, (fenceH + 0.3) / 2, pz)
      post.castShadow = true
      threeScene.add(post)
      // 立柱顶球
      const capGeo = new THREE.SphereGeometry(0.1, 6, 4)
      const cap = new THREE.Mesh(capGeo, fenceTopMat)
      cap.position.set(px, fenceH + 0.35, pz)
      threeScene.add(cap)
    }

    // 横栏（上下两根）
    const barGeo = new THREE.BoxGeometry(0.06, 0.06, len)
    for (const y of [0.5, fenceH]) {
      const bar = new THREE.Mesh(barGeo, fenceMat)
      bar.position.set((x1 + x2) / 2, y, (z1 + z2) / 2)
      bar.rotation.y = -angle
      threeScene.add(bar)
    }

    // 竖栅栏条
    const picketGeo = new THREE.BoxGeometry(0.04, fenceH - 0.3, 0.04)
    const picketCount = Math.floor(len / 0.5)
    for (let i = 1; i < picketCount; i++) {
      const t = i / picketCount
      const px = x1 + dx * t, pz = z1 + dz * t
      const picket = new THREE.Mesh(picketGeo, fenceMat)
      picket.position.set(px, (fenceH - 0.3) / 2 + 0.3, pz)
      threeScene.add(picket)
    }
  }

  // 大门位置：南面（z = fMaxZ）中间，宽度4
  const gateWidth = 4
  const gateCenterX = 0

  // 北面围栏（完整）
  createFenceSegment(fMinX, fMinZ, fMaxX, fMinZ)
  // 东面围栏（完整）
  createFenceSegment(fMaxX, fMinZ, fMaxX, fMaxZ)
  // 西面围栏（完整）
  createFenceSegment(fMinX, fMinZ, fMinX, fMaxZ)
  // 南面围栏（左段）
  createFenceSegment(fMinX, fMaxZ, gateCenterX - gateWidth / 2, fMaxZ)
  // 南面围栏（右段）
  createFenceSegment(gateCenterX + gateWidth / 2, fMaxZ, fMaxX, fMaxZ)

  // 大门
  const gatePostGeo = new THREE.BoxGeometry(0.3, fenceH + 1, 0.3)
  const gatePostMat = new THREE.MeshStandardMaterial({ color: 0x4a6a9a, roughness: 0.4, metalness: 0.6 })
  const gp1 = new THREE.Mesh(gatePostGeo, gatePostMat)
  gp1.position.set(gateCenterX - gateWidth / 2 - 0.15, (fenceH + 1) / 2, fMaxZ)
  threeScene.add(gp1)
  const gp2 = new THREE.Mesh(gatePostGeo, gatePostMat)
  gp2.position.set(gateCenterX + gateWidth / 2 + 0.15, (fenceH + 1) / 2, fMaxZ)
  threeScene.add(gp2)
  // 门柱顶球
  const gCapGeo = new THREE.SphereGeometry(0.2, 8, 6)
  const gCapMat = new THREE.MeshStandardMaterial({ color: 0x4facfe, metalness: 0.7, roughness: 0.3 })
  const gc1 = new THREE.Mesh(gCapGeo, gCapMat)
  gc1.position.set(gateCenterX - gateWidth / 2 - 0.15, fenceH + 1.2, fMaxZ)
  threeScene.add(gc1)
  const gc2 = new THREE.Mesh(gCapGeo, gCapMat)
  gc2.position.set(gateCenterX + gateWidth / 2 + 0.15, fenceH + 1.2, fMaxZ)
  threeScene.add(gc2)
  // 门柱横梁
  const gateBarGeo = new THREE.BoxGeometry(gateWidth + 0.6, 0.12, 0.12)
  const gateBar = new THREE.Mesh(gateBarGeo, gatePostMat)
  gateBar.position.set(gateCenterX, fenceH + 0.8, fMaxZ)
  threeScene.add(gateBar)
  // 门扇（两扇对开）
  const doorGeo = new THREE.BoxGeometry(gateWidth / 2 - 0.05, fenceH, 0.06)
  const doorMat = new THREE.MeshStandardMaterial({ color: 0x3a5a8a, roughness: 0.5, metalness: 0.5, transparent: true, opacity: 0.7 })
  const door1 = new THREE.Mesh(doorGeo, doorMat)
  door1.position.set(gateCenterX - gateWidth / 4, fenceH / 2, fMaxZ)
  threeScene.add(door1)
  const door2 = new THREE.Mesh(doorGeo, doorMat)
  door2.position.set(gateCenterX + gateWidth / 4, fenceH / 2, fMaxZ)
  threeScene.add(door2)
  // 门扇竖条
  const doorBarGeo = new THREE.BoxGeometry(0.04, fenceH - 0.2, 0.07)
  for (let i = 0; i < 4; i++) {
    const offset = -gateWidth / 4 + (i + 0.5) * (gateWidth / 2 - 0.1) / 4
    const db1 = new THREE.Mesh(doorBarGeo, fenceMat)
    db1.position.set(gateCenterX + offset, fenceH / 2, fMaxZ + 0.01)
    threeScene.add(db1)
    const db2 = new THREE.Mesh(doorBarGeo, fenceMat)
    db2.position.set(gateCenterX + gateWidth / 2 + offset, fenceH / 2, fMaxZ + 0.01)
    threeScene.add(db2)
  }
  // 门头文字区域（发光横牌）
  const signGeo = new THREE.BoxGeometry(gateWidth + 0.6, 0.6, 0.08)
  const signMat = new THREE.MeshBasicMaterial({ color: 0x4facfe, transparent: true, opacity: 0.25 })
  const sign = new THREE.Mesh(signGeo, signMat)
  sign.position.set(gateCenterX, fenceH + 1.6, fMaxZ)
  threeScene.add(sign)

  // 道路
  const roadGeo = new THREE.PlaneGeometry(3, 70)
  const roadMat = new THREE.MeshStandardMaterial({ color: 0x162a4a, roughness: 0.8 })
  const road1 = new THREE.Mesh(roadGeo, roadMat)
  road1.rotation.x = -Math.PI / 2
  road1.position.set(0, 0.01, 0)
  threeScene.add(road1)
  const road2 = new THREE.Mesh(new THREE.PlaneGeometry(70, 3), roadMat)
  road2.rotation.x = -Math.PI / 2
  road2.position.set(0, 0.01, 0)
  threeScene.add(road2)
  // 大门入口道路
  const gateRoadGeo = new THREE.PlaneGeometry(gateWidth, 6)
  const gateRoad = new THREE.Mesh(gateRoadGeo, roadMat)
  gateRoad.rotation.x = -Math.PI / 2
  gateRoad.position.set(0, 0.01, fMaxZ + 3)
  threeScene.add(gateRoad)

  // 路灯
  const lampPositions = [
    [-1.5, -10], [-1.5, 0], [-1.5, 10],
    [1.5, -10], [1.5, 0], [1.5, 10],
    [-10, 1.5], [10, 1.5]
  ]
  lampPositions.forEach(([x, z]) => {
    // 灯杆
    const poleGeo = new THREE.CylinderGeometry(0.05, 0.07, 4, 6)
    const poleMat = new THREE.MeshStandardMaterial({ color: 0x555555, metalness: 0.7 })
    const pole = new THREE.Mesh(poleGeo, poleMat)
    pole.position.set(x, 2, z)
    threeScene.add(pole)
    // 灯头臂
    const armGeo = new THREE.BoxGeometry(0.8, 0.05, 0.05)
    const arm = new THREE.Mesh(armGeo, poleMat)
    arm.position.set(x + 0.4, 4, z)
    threeScene.add(arm)
    // 灯头
    const headGeo = new THREE.BoxGeometry(0.5, 0.1, 0.3)
    const headMat = new THREE.MeshBasicMaterial({ color: 0xffeeaa, transparent: true, opacity: 0.6 })
    const head = new THREE.Mesh(headGeo, headMat)
    head.position.set(x + 0.8, 3.95, z)
    threeScene.add(head)
  })

  // 树木
  const treePositions = [
    [-24, -16], [-24, -8], [-24, 0], [-24, 8], [-24, 16],
    [24, -16], [24, -8], [24, 0], [24, 8], [24, 16],
    [-8, -20], [0, -20], [8, -20],
    [-8, 20], [0, 20], [8, 20],
    [-26, -12], [-26, 6], [26, -12], [26, 6]
  ]
  treePositions.forEach(([x, z]) => {
    const trunkGeo = new THREE.CylinderGeometry(0.15, 0.2, 1.5, 6)
    const trunkMat = new THREE.MeshStandardMaterial({ color: 0x3a2a1a })
    const trunk = new THREE.Mesh(trunkGeo, trunkMat)
    trunk.position.set(x, 0.75, z)
    threeScene.add(trunk)

    const crownGeo = new THREE.SphereGeometry(0.8, 8, 6)
    const crownMat = new THREE.MeshStandardMaterial({ color: 0x0a4a2a, roughness: 0.8 })
    const crown = new THREE.Mesh(crownGeo, crownMat)
    crown.position.set(x, 2.2, z)
    threeScene.add(crown)
  })

  // 停车位（4个区域，与parkingList数据联动）
  // 建筑集中在中心区域，停车位放在四角空地
  parkingSpotMeshes = {}
  const parkingZones = {
    'A': { baseX: -25, baseZ: -19, cols: 5, dir: 'x' },  // 西北角
    'B': { baseX: 15, baseZ: -19, cols: 5, dir: 'x' },   // 东北角
    'C': { baseX: -25, baseZ: 14, cols: 5, dir: 'x' },   // 西南角
    'D': { baseX: 15, baseZ: 14, cols: 5, dir: 'x' },    // 东南角
  }
  const spotW = 2.5, spotH = 4.5, spotGap = 0.3

  parkingList.forEach(spot => {
    const zone = spot.id.charAt(0)
    const num = parseInt(spot.id.split('-')[1]) - 1
    const zoneConf = parkingZones[zone]
    if (!zoneConf) return

    const col = num % zoneConf.cols
    const row = Math.floor(num / zoneConf.cols)
    let sx, sz
    if (zoneConf.dir === 'x') {
      // 列沿X排列，行沿Z排列
      sx = zoneConf.baseX + col * (spotW + spotGap)
      sz = zoneConf.baseZ + row * (spotH + spotGap)
    } else {
      sx = zoneConf.baseX + row * (spotW + spotGap)
      sz = zoneConf.baseZ + col * (spotH + spotGap)
    }

    // 停车位地面标记
    const spotGeo = new THREE.PlaneGeometry(spotW, spotH)
    const spotColor = spot.occupied ? 0xff4d6a : 0x00ff88
    const spotMat = new THREE.MeshBasicMaterial({
      color: spotColor, transparent: true, opacity: 0.15, side: THREE.DoubleSide
    })
    const spotMesh = new THREE.Mesh(spotGeo, spotMat)
    spotMesh.rotation.x = -Math.PI / 2
    spotMesh.position.set(sx, 0.02, sz)
    threeScene.add(spotMesh)

    // 停车位边框线
    const spotEdgeGeo = new THREE.EdgesGeometry(new THREE.PlaneGeometry(spotW, spotH))
    const spotEdgeMat = new THREE.LineBasicMaterial({ color: spotColor, transparent: true, opacity: 0.5 })
    const spotEdge = new THREE.LineSegments(spotEdgeGeo, spotEdgeMat)
    spotEdge.rotation.x = -Math.PI / 2
    spotEdge.position.set(sx, 0.03, sz)
    threeScene.add(spotEdge)

    // 停车位编号（用小平面模拟文字标记）
    const labelGeo = new THREE.PlaneGeometry(0.8, 0.4)
    const labelMat = new THREE.MeshBasicMaterial({ color: 0xa0cfff, transparent: true, opacity: 0.4, side: THREE.DoubleSide })
    const label = new THREE.Mesh(labelGeo, labelMat)
    label.rotation.x = -Math.PI / 2
    label.position.set(sx, 0.04, sz - spotH / 2 + 0.5)
    threeScene.add(label)

    // 车辆模型（仅占用车位显示）
    let carMesh = null
    if (spot.occupied) {
      carMesh = createCarMesh()
      carMesh.position.set(sx, 0, sz)
      threeScene.add(carMesh)
    }

    parkingSpotMeshes[spot.id] = { spot: spotMesh, edge: spotEdge, car: carMesh, label, sx, sz }
  })

  // 建筑物3D标签（Sprite，始终面向相机）
  parkTags.forEach(tag => {
    const canvas = document.createElement('canvas')
    canvas.width = 256
    canvas.height = 64
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = 'rgba(10,22,40,0.75)'
    ctx.roundRect(0, 0, 256, 64, 8)
    ctx.fill()
    ctx.strokeStyle = tag.status === 'warning' ? '#ffcc00' : '#4facfe'
    ctx.lineWidth = 2
    ctx.roundRect(0, 0, 256, 64, 8)
    ctx.stroke()
    ctx.fillStyle = tag.status === 'warning' ? '#ffcc00' : '#ffffff'
    ctx.font = 'bold 24px sans-serif'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(tag.name, 128, 32)

    const texture = new THREE.CanvasTexture(canvas)
    const spriteMat = new THREE.SpriteMaterial({ map: texture, transparent: true, opacity: 0.9 })
    const sprite = new THREE.Sprite(spriteMat)
    sprite.position.set(tag.x, tag.y + 1.5, tag.z)
    sprite.scale.set(4, 1, 1)
    threeScene.add(sprite)
  })

  // 初始应用日照
  updateDaylight()

  function animate() {
    animFrameId = requestAnimationFrame(animate)
    threeControls.update()
    threeRenderer.render(threeScene, threeCamera)
  }
  animate()
}

// ---- 更新日照 ----
function updateDaylight() {
  if (!threeScene || !dirLightRef || !ambientLightRef) return
  const now = new Date()
  const hour = debugHour.value !== null ? debugHour.value : now.getHours() + now.getMinutes() / 60
  const p = getDaylightParams(hour)

  // 天空颜色
  threeScene.background = new THREE.Color(rgbToHex(...p.skyColor))
  threeScene.fog.color = new THREE.Color(rgbToHex(...p.fogColor))

  // 环境光
  ambientLightRef.color = new THREE.Color(rgbToHex(...p.ambientColor))
  ambientLightRef.intensity = p.ambientIntensity

  // 方向光（太阳）
  dirLightRef.color = new THREE.Color(rgbToHex(...p.dirColor))
  dirLightRef.intensity = p.dirIntensity
  const sunRadius = 30
  const sunX = Math.cos(p.sunAngle) * sunRadius
  const sunY = Math.max(p.sunAltitude * sunRadius, 2)
  const sunZ = Math.sin(p.sunAngle) * sunRadius * 0.5
  dirLightRef.position.set(sunX, sunY, sunZ)

  // 地面颜色
  if (groundMeshRef) {
    groundMeshRef.material.color = new THREE.Color(rgbToHex(...p.groundColor))
  }

  // 窗户发光：夜间亮，白天暗
  windowMeshes.forEach(m => {
    m.material.opacity = p.windowOpacity
  })
}

function onDebugHourChange() {
  updateDaylight()
}

function formatDebugHour(h) {
  if (h === null || h === undefined) return '--:--'
  const hours = Math.floor(h) % 24
  const mins = Math.round((h - Math.floor(h)) * 60)
  return `${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}`
}

// ---- 传感器数据模拟更新 ----
function updateSensorData() {
  envSensors[0].value = +(25 + Math.random() * 4).toFixed(1)
  envSensors[1].value = +(55 + Math.random() * 15).toFixed(1)
  envSensors[2].value = Math.round(25 + Math.random() * 30)
  envSensors[3].value = Math.round(35 + Math.random() * 20)
  envSensors[4].value = +(2 + Math.random() * 5).toFixed(1)
  envSensors[5].value = Math.round(700 + Math.random() * 300)
}

function updateTime() {
  const now = new Date()
  const week = ['星期日','星期一','星期二','星期三','星期四','星期五','星期六'][now.getDay()]
  currentTime.value = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')} ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')} ${week}`
  updateDaylight()
}

function handleResize() {
  if (threeRenderer && threeCamera) {
    const container = threeRef.value
    const w = container.clientWidth
    const h = container.clientHeight
    threeCamera.aspect = w / h
    threeCamera.updateProjectionMatrix()
    threeRenderer.setSize(w, h)
  }
}

onMounted(async () => {
  updateTime()
  timer = setInterval(updateTime, 1000)
  await nextTick()
  initThree()
  loadCameras()
  for (let i = 0; i < 6; i++) addAlarm()
  alarmTimer = setInterval(() => {
    addAlarm()
    updateSensorData()
    updateGateStats()
  }, 4000)
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  clearInterval(timer)
  clearInterval(alarmTimer)
  window.removeEventListener('resize', handleResize)
  destroyModalFlvPlayer()
  if (animFrameId) cancelAnimationFrame(animFrameId)
  threeRenderer?.dispose()
  threeControls?.dispose()
})
</script>

<style scoped>
.smart-park {
  width: 100vw; height: 100vh;
  background: #060e1a;
  color: #a0cfff;
  font-family: 'Microsoft YaHei', sans-serif;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  position: relative;
}

/* ---- 顶部标题 ---- */
.park-header {
  height: 80px;
  display: flex; align-items: center; justify-content: center;
  position: relative; z-index: 10;
  background: linear-gradient(180deg, rgba(6,14,26,0.97) 0%, rgba(6,14,26,0.5) 80%, transparent 100%);
  flex-shrink: 0;
  pointer-events: none;
}
.header-side { flex: 1; display: flex; align-items: center; height: 100%; padding: 0 30px; }
.header-side.left { justify-content: flex-end; }
.header-side.right { justify-content: flex-start; }
.header-wing {
  width: 16px; height: 16px;
  border: 2px solid rgba(79,172,254,0.7);
  transform: rotate(45deg);
  background: rgba(79,172,254,0.08);
  flex-shrink: 0;
  box-shadow: 0 0 8px rgba(79,172,254,0.3);
}
.header-line { flex: 1; height: 1px; position: relative; }
.header-line::before {
  content: ''; position: absolute; top: 0; width: 100%; height: 1px;
  background: linear-gradient(90deg, rgba(79,172,254,0.6), rgba(79,172,254,0.05));
}
.header-side.right .header-line::before {
  background: linear-gradient(90deg, rgba(79,172,254,0.05), rgba(79,172,254,0.6));
}
.header-center { text-align: center; padding: 0 10px; cursor: pointer; pointer-events: auto; flex-shrink: 0; }
.header-frame { position: relative; padding: 8px 50px; }
.header-frame .corner { position: absolute; width: 18px; height: 18px; }
.header-frame .corner::before, .header-frame .corner::after {
  content: ''; position: absolute; background: #4facfe; box-shadow: 0 0 6px rgba(79,172,254,0.5);
}
.header-frame .corner::before { width: 18px; height: 2px; }
.header-frame .corner::after { width: 2px; height: 18px; }
.header-frame .corner.tl { top:0;left:0; } .header-frame .corner.tl::before { top:0;left:0; } .header-frame .corner.tl::after { top:0;left:0; }
.header-frame .corner.tr { top:0;right:0; } .header-frame .corner.tr::before { top:0;right:0; } .header-frame .corner.tr::after { top:0;right:0; }
.header-frame .corner.bl { bottom:0;left:0; } .header-frame .corner.bl::before { bottom:0;left:0; } .header-frame .corner.bl::after { bottom:0;left:0; }
.header-frame .corner.br { bottom:0;right:0; } .header-frame .corner.br::before { bottom:0;right:0; } .header-frame .corner.br::after { bottom:0;right:0; }
.header-title {
  font-size: 30px; font-weight: 700; letter-spacing: 8px;
  background: linear-gradient(180deg, #fff 0%, #4facfe 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  margin: 0; filter: drop-shadow(0 0 12px rgba(79,172,254,0.4));
}
.header-time { font-size: 13px; color: rgba(79,172,254,0.7); margin-top: 2px; letter-spacing: 2px; }

/* ---- 主体布局 ---- */
.park-body {
  flex: 1;
  display: grid;
  grid-template-columns: 22% 1fr 22%;
  grid-template-rows: 1fr auto;
  gap: 10px;
  padding: 0 10px 10px;
  position: relative; z-index: 5;
  min-height: 0;
  pointer-events: none;
}

.side-col {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
  pointer-events: none;
}
.left-col { grid-column: 1; grid-row: 1 / 3; }
.right-col { grid-column: 3; grid-row: 1 / 3; }

.center-col {
  grid-column: 2; grid-row: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
  pointer-events: none;
}

/* ---- 面板 ---- */
.panel {
  flex: 1;
  min-height: 0;
  background: rgba(10,22,40,0.6);
  backdrop-filter: blur(6px);
  border: 1px solid rgba(79,172,254,0.2);
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  pointer-events: auto;
  position: relative;
}
.panel::before, .panel::after {
  content: ''; position: absolute; width: 12px; height: 12px;
  border-color: rgba(79,172,254,0.5); border-style: solid;
}
.panel::before { top: -1px; left: -1px; border-width: 2px 0 0 2px; }
.panel::after { bottom: -1px; right: -1px; border-width: 0 2px 2px 0; }

.panel-header {
  font-size: 13px; font-weight: 600; color: #4facfe;
  margin-bottom: 8px;
  display: flex; align-items: center; gap: 6px;
  flex-shrink: 0;
}
.title-dot {
  width: 6px; height: 6px;
  background: #4facfe;
  box-shadow: 0 0 6px #4facfe;
  display: inline-block;
  clip-path: polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%);
}
.panel-body { flex: 1; min-height: 0; overflow: hidden; }

/* ---- 传感器网格 ---- */
.sensor-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  height: 100%;
  align-content: start;
}
.sensor-card {
  display: flex; align-items: center; gap: 8px;
  padding: 8px;
  border: 1px solid rgba(79,172,254,0.1);
  position: relative;
}
.sensor-card::before, .sensor-card::after {
  content: ''; position: absolute; width: 6px; height: 6px;
  border-color: rgba(79,172,254,0.3); border-style: solid;
}
.sensor-card::before { top: -1px; left: -1px; border-width: 1px 0 0 1px; }
.sensor-card::after { bottom: -1px; right: -1px; border-width: 0 1px 1px 0; }
.sensor-icon { font-size: 22px; flex-shrink: 0; }
.sensor-info { flex: 1; }
.sensor-value { font-size: 18px; font-weight: 700; font-family: 'DIN','Courier New',monospace; }
.sensor-unit { font-size: 10px; opacity: 0.6; margin-left: 2px; }
.sensor-label { font-size: 11px; color: rgba(160,207,255,0.6); margin-top: 2px; }
.sensor-status {
  font-size: 10px; padding: 1px 6px;
  border-radius: 2px;
  flex-shrink: 0;
}
.sensor-status.normal { color: #00ff88; background: rgba(0,255,136,0.1); }

/* ---- 告警列表 ---- */
.alarm-list { flex: 1; overflow: hidden; font-size: 12px; }
.alarm-row {
  display: flex; padding: 5px 4px;
  border-bottom: 1px solid rgba(79,172,254,0.06);
  transition: background 0.5s;
}
.alarm-row span { flex: 1; text-align: center; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.alarm-header { color: #4facfe; font-weight: 600; border-bottom-color: rgba(79,172,254,0.2); }
.alarm-new { background: rgba(79,172,254,0.08); }
.level-critical { color: #ff4d6a; }
.level-warning { color: #ffcc00; }

/* ---- 3D 园区 ---- */
.three-d-area {
  flex: 1;
  position: relative;
  min-height: 0;
  pointer-events: auto;
  border: 1px solid rgba(79,172,254,0.15);
}
.three-container {
  width: 100%; height: 100%;
}

/* ---- 日照调试滑块 ---- */
.daylight-debug {
  position: absolute;
  bottom: 8px; left: 50%;
  transform: translateX(-50%);
  display: flex; align-items: center; gap: 8px;
  background: rgba(10,22,40,0.85);
  border: 1px solid rgba(79,172,254,0.4);
  padding: 6px 14px;
  border-radius: 4px;
  z-index: 10;
  pointer-events: auto;
  font-size: 12px;
  color: #a0cfff;
}
.daylight-debug label {
  color: #4facfe; font-weight: 600; white-space: nowrap;
}
.daylight-debug input[type="range"] {
  width: 200px;
  accent-color: #4facfe;
  cursor: pointer;
}
.debug-time {
  color: #fff; font-weight: 700;
  font-family: 'DIN','Courier New',monospace;
  min-width: 46px; text-align: center;
}
.debug-reset {
  background: rgba(79,172,254,0.15);
  border: 1px solid rgba(79,172,254,0.4);
  color: #4facfe; font-size: 11px;
  padding: 2px 8px; cursor: pointer;
  border-radius: 2px;
  white-space: nowrap;
  transition: all 0.2s;
}
.debug-reset:hover {
  background: rgba(79,172,254,0.3);
  color: #fff;
}

/* ---- 摄像头栏 ---- */
.camera-bar {
  display: flex;
  gap: 8px;
  height: 140px;
  flex-shrink: 0;
  pointer-events: auto;
  overflow-x: auto;
  overflow-y: hidden;
  padding-bottom: 4px;
}
.camera-bar::-webkit-scrollbar {
  height: 4px;
}
.camera-bar::-webkit-scrollbar-track {
  background: rgba(79,172,254,0.1);
}
.camera-bar::-webkit-scrollbar-thumb {
  background: rgba(79,172,254,0.4);
  border-radius: 2px;
}
.camera-item {
  flex: 0 0 160px;
  display: flex;
  flex-direction: column;
  cursor: pointer;
  border: 1px solid rgba(79,172,254,0.2);
  background: rgba(10,22,40,0.6);
  transition: all 0.3s;
  overflow: hidden;
  flex-shrink: 0;
}
.camera-item:hover, .camera-item.active {
  border-color: #4facfe;
  box-shadow: 0 0 12px rgba(79,172,254,0.3);
}
.camera-feed {
  flex: 1;
  background: #0a1628;
  display: flex; align-items: center; justify-content: center;
  overflow: hidden;
  position: relative;
}
.camera-feed video { width: 100%; height: 100%; object-fit: cover; }
.camera-placeholder {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  color: rgba(160,207,255,0.4); font-size: 11px;
}
.camera-label {
  padding: 3px 8px;
  font-size: 11px;
  color: #a0cfff;
  display: flex; align-items: center; gap: 4px;
  background: rgba(10,22,40,0.8);
}
.cam-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: #666;
}
.cam-dot.online { background: #00ff88; box-shadow: 0 0 4px #00ff88; }

/* ---- 概览网格 ---- */
.overview-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  height: 100%;
  align-content: center;
}
.overview-item {
  text-align: center;
  padding: 10px 6px;
  border: 1px solid rgba(79,172,254,0.1);
  position: relative;
}
.overview-item::before, .overview-item::after {
  content: ''; position: absolute; width: 6px; height: 6px;
  border-color: rgba(79,172,254,0.3); border-style: solid;
}
.overview-item::before { top: -1px; left: -1px; border-width: 1px 0 0 1px; }
.overview-item::after { bottom: -1px; right: -1px; border-width: 0 1px 1px 0; }
.overview-num {
  font-size: 22px; font-weight: 700;
  font-family: 'DIN','Courier New',monospace;
  text-shadow: 0 0 10px currentColor;
}
.overview-label { font-size: 11px; color: rgba(160,207,255,0.6); margin-top: 4px; }

/* ---- 停车位 ---- */
.parking-panel { flex: 2 !important; }
.parking-summary {
  margin-left: auto;
  font-size: 11px;
  color: rgba(160,207,255,0.6);
  font-weight: 400;
}
.parking-lot {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  overflow-y: auto;
  height: 100%;
  padding-right: 2px;
}
.parking-lot::-webkit-scrollbar { width: 3px; }
.parking-lot::-webkit-scrollbar-track { background: rgba(79,172,254,0.05); }
.parking-lot::-webkit-scrollbar-thumb { background: rgba(79,172,254,0.3); border-radius: 2px; }
.parking-spot {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 8px;
  border: 1px solid rgba(79,172,254,0.1);
  background: rgba(0,255,136,0.03);
  transition: all 0.3s;
}
.parking-spot.occupied {
  background: rgba(255,77,106,0.06);
  border-color: rgba(255,77,106,0.2);
}
.parking-spot.highlighted {
  border-color: #ffff00 !important;
  background: rgba(255,255,0,0.1) !important;
  box-shadow: 0 0 8px rgba(255,255,0,0.3);
  cursor: pointer;
}
.parking-spot {
  cursor: pointer;
}
.spot-icon {
  width: 28px; height: 28px;
  display: flex; align-items: center; justify-content: center;
  font-size: 16px;
  border-radius: 4px;
  flex-shrink: 0;
}
.parking-spot.occupied .spot-icon {
  color: #ff4d6a;
  background: rgba(255,77,106,0.12);
}
.parking-spot:not(.occupied) .spot-icon {
  color: #00ff88;
  background: rgba(0,255,136,0.1);
}
.spot-empty {
  font-size: 13px; font-weight: 700;
  font-family: 'DIN','Courier New',monospace;
}
.spot-info { flex: 1; min-width: 0; }
.spot-id {
  font-size: 11px; font-weight: 600; color: #a0cfff;
  font-family: 'DIN','Courier New',monospace;
}
.spot-status {
  font-size: 10px; margin-top: 1px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.spot-status.busy { color: #ff4d6a; }
.spot-status.free { color: #00ff88; }

/* ---- 大门门禁统计 ---- */
.gate-panel { flex: 1.2 !important; }
.gate-stats { display: flex; flex-direction: column; gap: 8px; height: 100%; }
.gate-stat-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}
.gate-stat-item {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 8px;
  border: 1px solid rgba(79,172,254,0.1);
}
.gate-stat-item.person-in { border-left: 2px solid #00ff88; }
.gate-stat-item.person-out { border-left: 2px solid #4facfe; }
.gate-stat-item.car-in { border-left: 2px solid #ffcc00; }
.gate-stat-item.car-out { border-left: 2px solid #ff4d6a; }
.gate-icon {
  width: 28px; height: 28px;
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; color: #4facfe;
  background: rgba(79,172,254,0.1); border-radius: 4px;
}
.gate-num {
  font-size: 18px; font-weight: 700;
  font-family: 'DIN','Courier New',monospace;
  color: #fff; line-height: 1.2;
}
.gate-label { font-size: 10px; color: rgba(160,207,255,0.6); }
.gate-plates { flex: 1; display: flex; flex-direction: column; min-height: 0; }
.plates-title {
  font-size: 11px; color: rgba(160,207,255,0.6);
  margin-bottom: 4px;
}
.plates-list {
  display: flex; flex-wrap: wrap; gap: 4px;
  overflow-y: auto; flex: 1;
}
.plates-list::-webkit-scrollbar { width: 3px; }
.plates-list::-webkit-scrollbar-thumb { background: rgba(79,172,254,0.3); }
.plate-tag {
  font-size: 11px; font-weight: 600;
  color: #00e5ff;
  background: rgba(0,229,255,0.08);
  border: 1px solid rgba(0,229,255,0.2);
  padding: 2px 6px;
  font-family: 'DIN','Courier New',monospace;
  white-space: nowrap;
}

/* ---- 设备状态 ---- */
.device-panel { flex: 1.2 !important; }
.device-tabs {
  display: flex; gap: 4px; margin-bottom: 8px;
}
.device-tabs button {
  flex: 1; padding: 4px 0;
  font-size: 11px; color: #a0cfff;
  background: rgba(79,172,254,0.05);
  border: 1px solid rgba(79,172,254,0.15);
  cursor: pointer; transition: all 0.3s;
}
.device-tabs button:hover { background: rgba(79,172,254,0.12); }
.device-tabs button.active {
  background: rgba(79,172,254,0.2);
  border-color: #4facfe; color: #fff;
}
.device-grid {
  display: flex; flex-direction: column; gap: 4px;
  overflow-y: auto; flex: 1;
}
.device-grid::-webkit-scrollbar { width: 3px; }
.device-grid::-webkit-scrollbar-thumb { background: rgba(79,172,254,0.3); }
.device-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 5px 8px;
  border-bottom: 1px solid rgba(79,172,254,0.06);
}
.device-id {
  font-size: 12px; font-weight: 600; color: #a0cfff;
  font-family: 'DIN','Courier New',monospace;
}
.device-loc { font-size: 10px; color: rgba(160,207,255,0.5); margin-top: 1px; }
.device-state {
  font-size: 11px; padding: 2px 8px;
  font-weight: 600;
}
.device-state.on { color: #00ff88; background: rgba(0,255,136,0.08); }
.device-state.off { color: #ff4d6a; background: rgba(255,77,106,0.08); }

/* ---- 摄像头弹窗 ---- */
.camera-modal {
  position: fixed; top: 0; left: 0;
  width: 100%; height: 100%;
  background: rgba(0,0,0,0.7);
  z-index: 1000;
  display: flex; align-items: center; justify-content: center;
  pointer-events: auto;
}
.modal-content {
  width: 70%; max-height: 80%;
  background: #0a1628;
  border: 1px solid rgba(79,172,254,0.4);
  display: flex; flex-direction: column;
}
.modal-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px;
  border-bottom: 1px solid rgba(79,172,254,0.2);
  color: #4facfe; font-size: 14px;
}
.modal-close { cursor: pointer; font-size: 16px; color: #a0cfff; }
.modal-close:hover { color: #fff; }
.modal-body {
  flex: 1;
  display: flex; align-items: center; justify-content: center;
  background: #060e1a;
  min-height: 400px;
}
.modal-body video, .modal-video { width: 100%; height: 100%; object-fit: contain; }
.modal-footer {
  display: flex; align-items: center; justify-content: center;
  padding: 10px 16px;
  border-top: 1px solid rgba(79,172,254,0.2);
}
.stream-btn {
  padding: 6px 20px;
  background: rgba(79,172,254,0.15);
  border: 1px solid rgba(79,172,254,0.4);
  color: #4facfe;
  cursor: pointer;
  font-size: 13px;
  display: flex; align-items: center; gap: 6px;
  transition: all 0.3s;
}
.stream-btn:hover {
  background: rgba(79,172,254,0.25);
  border-color: #4facfe;
}
.stream-btn.stop {
  color: #ff6b6b;
  border-color: rgba(255,107,107,0.4);
  background: rgba(255,107,107,0.1);
}
.stream-btn.stop:hover {
  background: rgba(255,107,107,0.2);
  border-color: #ff6b6b;
}
.camera-placeholder.large {
  width: 100%;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px;
  color: rgba(160,207,255,0.3); font-size: 16px;
}
</style>
