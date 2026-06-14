<template>
  <div class="camera-live">
    <div class="live-header">
      <a-space>
        <a-button @click="$router.back()"><LeftOutlined /> 返回</a-button>
        <span class="camera-name">{{ cameraInfo.name || '摄像头监控' }}</span>
        <a-badge :status="cameraInfo.is_online ? 'success' : 'default'" :text="cameraInfo.is_online ? '在线' : '离线'" />
      </a-space>
      <a-space>
        <a-button @click="handleSnapshot" :loading="snapshotLoading" :disabled="!cameraInfo.is_online">
          <CameraOutlined /> 抓图
        </a-button>
        <a-button
          :type="streamRunning ? 'default' : 'primary'"
          @click="toggleStream"
          :loading="streamLoading"
          :disabled="!cameraInfo.is_online"
        >
          <VideoCameraOutlined /> {{ streamRunning ? '停止流' : '启动流' }}
        </a-button>
      </a-space>
    </div>

    <div class="live-body">
      <!-- 视频区域 -->
      <div class="video-area">
        <div class="video-container" ref="videoContainerRef">
          <video ref="videoRef" class="video-player" muted></video>
          <div class="video-overlay" v-if="!streamRunning">
            <div class="overlay-content">
              <VideoCameraOutlined style="font-size: 48px; opacity: 0.3" />
              <p>{{ streamLoading ? '正在连接...' : '点击"启动流"开始播放' }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- 云台控制 -->
      <div class="ptz-panel">
        <div class="panel-title">云台控制</div>
        <div class="ptz-direction">
          <div class="ptz-row">
            <a-button class="ptz-btn" @mousedown="ptzMove(0, 0.5, 0)" @mouseup="ptzStopMove" :disabled="!cameraInfo.is_online">
              <CaretUpOutlined />
            </a-button>
          </div>
          <div class="ptz-row">
            <a-button class="ptz-btn" @mousedown="ptzMove(-0.5, 0, 0)" @mouseup="ptzStopMove" :disabled="!cameraInfo.is_online">
              <CaretLeftOutlined />
            </a-button>
            <a-button class="ptz-btn ptz-center" @click="ptzStopMove" :disabled="!cameraInfo.is_online">
              <StopOutlined />
            </a-button>
            <a-button class="ptz-btn" @mousedown="ptzMove(0.5, 0, 0)" @mouseup="ptzStopMove" :disabled="!cameraInfo.is_online">
              <CaretRightOutlined />
            </a-button>
          </div>
          <div class="ptz-row">
            <a-button class="ptz-btn" @mousedown="ptzMove(0, -0.5, 0)" @mouseup="ptzStopMove" :disabled="!cameraInfo.is_online">
              <CaretDownOutlined />
            </a-button>
          </div>
        </div>
        <div class="ptz-zoom">
          <span>变焦</span>
          <a-button @mousedown="ptzMove(0, 0, 0.5)" @mouseup="ptzStopMove" :disabled="!cameraInfo.is_online">
            <ZoomInOutlined />
          </a-button>
          <a-button @mousedown="ptzMove(0, 0, -0.5)" @mouseup="ptzStopMove" :disabled="!cameraInfo.is_online">
            <ZoomOutOutlined />
          </a-button>
        </div>

        <div class="panel-title" style="margin-top: 16px">速度</div>
        <a-slider v-model:value="ptzSpeed" :min="0.1" :max="1" :step="0.1" />

        <div class="panel-title" style="margin-top: 16px">预置位</div>
        <div class="preset-list">
          <a-button
            v-for="i in 4"
            :key="i"
            size="small"
            @click="gotoPreset(String(i))"
            :disabled="!cameraInfo.is_online"
          >
            预置位 {{ i }}
          </a-button>
        </div>

        <div class="panel-title" style="margin-top: 16px">抓图记录</div>
        <div class="snapshot-list">
          <a-empty v-if="snapshots.length === 0" description="暂无抓图" />
          <div v-for="snap in snapshots" :key="snap.filename" class="snapshot-item">
            <span class="snap-name">{{ snap.filename }}</span>
            <a-button type="link" size="small" @click="downloadSnapshot(snap.filename)">下载</a-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import { message } from 'ant-design-vue'
import { useRoute } from 'vue-router'
import {
  LeftOutlined, CameraOutlined, VideoCameraOutlined,
  CaretUpOutlined, CaretDownOutlined, CaretLeftOutlined, CaretRightOutlined,
  StopOutlined, ZoomInOutlined, ZoomOutOutlined
} from '@ant-design/icons-vue'
import {
  getCamera, connectCamera, snapshotCamera,
  startStream, stopStream, getStreamStatus,
  ptzControl, ptzStop as ptzStopApi, ptzPreset
} from '@/api/camera'
import flvjs from 'flv.js/dist/flv.min.js'

const route = useRoute()
const cameraId = Number(route.params.id)

const cameraInfo = reactive({
  name: '',
  ip: '',
  is_online: false,
  rtsp_url: ''
})

const videoRef = ref(null)
const videoContainerRef = ref(null)
const streamRunning = ref(false)
const streamLoading = ref(false)
const snapshotLoading = ref(false)
const ptzSpeed = ref(0.5)
const snapshots = ref([])

let flvPlayer = null

async function loadCamera() {
  try {
    const res = await getCamera(cameraId)
    Object.assign(cameraInfo, res.data)
  } catch (e) {
    message.error('获取摄像头信息失败')
  }
}

async function toggleStream() {
  if (streamRunning.value) {
    await handleStopStream()
  } else {
    await handleStartStream()
  }
}

async function handleStartStream() {
  streamLoading.value = true
  try {
    // 如果不在线先连接
    if (!cameraInfo.is_online) {
      await connectCamera(cameraId)
      await loadCamera()
    }
    await startStream(cameraId)
    // start_stream 后端已做健康检查，无需额外等待
    initFlvPlayer()
    streamRunning.value = true
    message.success('视频流已启动')
  } catch (e) {
    message.error('启动视频流失败')
  } finally {
    streamLoading.value = false
  }
}

async function handleStopStream() {
  streamLoading.value = true
  try {
    destroyFlvPlayer()
    await stopStream(cameraId)
    streamRunning.value = false
    message.success('视频流已停止')
  } catch (e) {
    message.error('停止视频流失败')
  } finally {
    streamLoading.value = false
  }
}

function initFlvPlayer() {
  if (!flvjs.isSupported()) {
    message.error('当前浏览器不支持FLV播放')
    return
  }
  destroyFlvPlayer()

  const videoElement = videoRef.value
  if (!videoElement) {
    message.error('视频元素未就绪')
    return
  }
  const token = localStorage.getItem('access_token')
  flvPlayer = flvjs.createPlayer({
    type: 'flv',
    url: `/api/v1/cameras/${cameraId}/stream/live.flv`,
    isLive: true,
    hasAudio: false,
    hasVideo: true,
    cors: true,
  }, {
    enableStashBuffer: true,
    stashInitialSize: 1024,
    autoCleanupSourceBuffer: true,
    autoCleanupMaxBackwardDuration: 3,
    autoCleanupMinBackwardDuration: 2,
    lazyLoadMaxDuration: 3 * 60,
    headers: token ? { 'Authorization': `Bearer ${token}` } : {},
  })

  flvPlayer.attachMediaElement(videoElement)
  flvPlayer.load()
  flvPlayer.play().catch((e) => {
    console.warn('自动播放被阻止，需要用户交互:', e)
  })

  flvPlayer.on(flvjs.Events.ERROR, (errType, errDetail, errInfo) => {
    console.error('FLV error:', errType, errDetail, errInfo)
    message.error(`视频流错误: ${errDetail}`)
  })
}

function destroyFlvPlayer() {
  if (flvPlayer) {
    try {
      flvPlayer.pause()
      flvPlayer.unload()
      flvPlayer.detachMediaElement()
      flvPlayer.destroy()
    } catch (e) {
      // ignore
    }
    flvPlayer = null
  }
}

// 云台控制
function ptzMove(pan, tilt, zoom) {
  const speed = ptzSpeed.value
  ptzControl(cameraId, {
    pan: pan * speed,
    tilt: tilt * speed,
    zoom: zoom * speed
  }).catch(() => {})
}

function ptzStopMove() {
  ptzStopApi(cameraId).catch(() => {})
}

function gotoPreset(token) {
  ptzPreset(cameraId, token).then(() => {
    message.success(`已切换到预置位 ${token}`)
  }).catch(() => {
    message.error('预置位调用失败')
  })
}

// 抓图
async function handleSnapshot() {
  snapshotLoading.value = true
  try {
    const res = await snapshotCamera(cameraId)
    snapshots.value.unshift(res.data)
    if (snapshots.value.length > 10) snapshots.value.pop()
    message.success('抓图成功')
  } catch (e) {
    message.error('抓图失败')
  } finally {
    snapshotLoading.value = false
  }
}

function downloadSnapshot(filename) {
  window.open(`/api/v1/cameras/${cameraId}/snapshot/${filename}`, '_blank')
}

onMounted(async () => {
  await loadCamera()
})

onBeforeUnmount(() => {
  destroyFlvPlayer()
})
</script>

<style scoped>
.camera-live {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.live-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #fff;
  border-bottom: 1px solid #f0f0f0;
}

.camera-name {
  font-size: 16px;
  font-weight: 600;
}

.live-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.video-area {
  flex: 1;
  padding: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #1a1a2e;
}

.video-container {
  position: relative;
  width: 100%;
  max-width: 960px;
  aspect-ratio: 16 / 9;
  background: #000;
  border-radius: 4px;
  overflow: hidden;
}

.video-player {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.video-overlay {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.5);
}

.overlay-content {
  text-align: center;
  color: rgba(255, 255, 255, 0.6);
}

.overlay-content p {
  margin-top: 12px;
  font-size: 14px;
}

.ptz-panel {
  width: 240px;
  padding: 16px;
  background: #fff;
  border-left: 1px solid #f0f0f0;
  overflow-y: auto;
}

.panel-title {
  font-size: 13px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
}

.ptz-direction {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.ptz-row {
  display: flex;
  gap: 4px;
}

.ptz-btn {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
}

.ptz-center {
  background: #f5f5f5;
}

.ptz-zoom {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  justify-content: center;
}

.ptz-zoom span {
  font-size: 13px;
  color: #666;
}

.preset-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.snapshot-list {
  max-height: 200px;
  overflow-y: auto;
}

.snapshot-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  border-bottom: 1px solid #f5f5f5;
}

.snap-name {
  font-size: 12px;
  color: #666;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 130px;
}
</style>
