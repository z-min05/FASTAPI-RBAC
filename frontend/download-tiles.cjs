/**
 * 离线瓦片下载脚本
 * 下载高德地图暗色风格瓦片，用于大屏离线展示
 *
 * 使用方法：
 *   node download-tiles.cjs          # 下载所有范围
 *   node download-tiles.cjs gz       # 只下载广州高清瓦片 (zoom 9-16)
 *   node download-tiles.cjs cn       # 只下载全国概览瓦片 (zoom 3-8)
 *
 * 瓦片将保存到 frontend/public/map/tiles/{z}/{x}/{y}.png
 */

const http = require('http')
const https = require('https')
const fs = require('fs')
const path = require('path')

// 全国概览：zoom 5-8（经度 73°~136°, 纬度 3°~54°）
const CHINA_TILES = {
  5: { xMin: 22, xMax: 28, yMin: 10, yMax: 22 },
  6: { xMin: 44, xMax: 56, yMin: 21, yMax: 44 },
  7: { xMin: 89, xMax: 112, yMin: 42, yMax: 88 },
  8: { xMin: 178, xMax: 224, yMin: 84, yMax: 176 }
}

// 广州高清：zoom 9-16（经度 112.9°~114.4°, 纬度 22.5°~23.9°）
const GUANGZHOU_TILES = {
  9:  { xMin: 416, xMax: 418, yMin: 221, yMax: 223 },
  10: { xMin: 833, xMax: 836, yMin: 443, yMax: 446 },
  11: { xMin: 1666, xMax: 1673, yMin: 886, yMax: 893 },
  12: { xMin: 3333, xMax: 3346, yMin: 1773, yMax: 1787 },
  13: { xMin: 6667, xMax: 6693, yMin: 3547, yMax: 3575 },
  14: { xMin: 13334, xMax: 13387, yMin: 7095, yMax: 7151 },
  15: { xMin: 26669, xMax: 26775, yMin: 14190, yMax: 14303 },
  16: { xMin: 53338, xMax: 53551, yMin: 28381, yMax: 28607 }
}

// 高德地图暗色风格（国内服务器，速度快）
function getTileUrl(z, x, y) {
  const s = (x + y) % 4 + 1
  return `http://webrd0${s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x=${x}&y=${y}&z=${z}`
}

const OUTPUT_DIR = path.join(__dirname, 'public', 'map', 'tiles')

const CONCURRENCY = 30
const RETRY = 3

function downloadTile(z, x, y, retry = 0) {
  return new Promise((resolve, reject) => {
    const url = getTileUrl(z, x, y)
    const dir = path.join(OUTPUT_DIR, String(z), String(x))
    const filePath = path.join(dir, `${y}.png`)

    if (fs.existsSync(filePath)) {
      resolve('skip')
      return
    }

    fs.mkdirSync(dir, { recursive: true })

    const file = fs.createWriteStream(filePath)
    const client = url.startsWith('https') ? https : http
    client.get(url, { timeout: 15000 }, (res) => {
      if (res.statusCode !== 200) {
        file.close()
        if (fs.existsSync(filePath)) fs.unlinkSync(filePath)
        if (retry < RETRY) {
          resolve(downloadTile(z, x, y, retry + 1))
        } else {
          reject(new Error(`HTTP ${res.statusCode} for ${url}`))
        }
        return
      }
      res.pipe(file)
      file.on('finish', () => {
        file.close()
        resolve('ok')
      })
    }).on('error', () => {
      file.close()
      if (fs.existsSync(filePath)) fs.unlinkSync(filePath)
      if (retry < RETRY) {
        resolve(downloadTile(z, x, y, retry + 1))
      } else {
        reject(new Error(`Failed: ${url}`))
      }
    })
  })
}

async function run() {
  const arg = process.argv[2] || ''
  let tileRanges

  if (arg === 'gz') {
    tileRanges = GUANGZHOU_TILES
    console.log('模式：广州高清瓦片 (zoom 9-16)')
  } else if (arg === 'cn') {
    tileRanges = CHINA_TILES
    console.log('模式：全国概览瓦片 (zoom 3-8)')
  } else {
    tileRanges = { ...CHINA_TILES, ...GUANGZHOU_TILES }
    console.log('模式：全部（全国概览 + 广州高清）')
  }

  const tasks = []
  for (const [z, range] of Object.entries(tileRanges)) {
    for (let x = range.xMin; x <= range.xMax; x++) {
      for (let y = range.yMin; y <= range.yMax; y++) {
        tasks.push({ z: Number(z), x, y })
      }
    }
  }

  console.log(`共 ${tasks.length} 个瓦片需要下载`)
  fs.mkdirSync(OUTPUT_DIR, { recursive: true })

  let completed = 0
  let skipped = 0
  let failed = 0

  const executing = new Set()
  for (const task of tasks) {
    const p = downloadTile(task.z, task.x, task.y)
      .then(result => {
        if (result === 'skip') skipped++
        else completed++
      })
      .catch(() => {
        failed++
      })
      .finally(() => {
        executing.delete(p)
      })
    executing.add(p)

    if (executing.size >= CONCURRENCY) {
      await Promise.race(executing)
    }

    const progress = completed + skipped + failed
    if (progress % 100 === 0 || progress === tasks.length) {
      process.stdout.write(`\r进度: ${progress}/${tasks.length} (下载:${completed} 跳过:${skipped} 失败:${failed})`)
    }
  }

  await Promise.all(executing)
  console.log(`\n完成! 下载:${completed} 跳过:${skipped} 失败:${failed}`)
}

run().catch(console.error)
