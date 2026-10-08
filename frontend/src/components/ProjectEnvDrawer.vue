<template>
  <a-drawer
    :open="open"
    :width="980"
    :title="`自动化测试环境 — ${project?.name || ''}`"
    destroy-on-close
    @close="handleClose"
  >
    <a-spin :spinning="loading">
      <!-- 顶部状态条：漂移提示 / 当前生效环境 -->
      <a-alert
        v-if="list.drifted"
        type="warning"
        show-icon
        class="env-alert"
        message="当前 .env 与所有环境快照都不一致（有未归档修改）"
      >
        <template #description>
          <a-space wrap>
            <a-button size="small" v-permission="'project:env:create'" @click="openCreate">
              另存为新环境
            </a-button>
            <a-button size="small" @click="selectActiveFile">查看/编辑当前 .env</a-button>
          </a-space>
        </template>
      </a-alert>
      <div v-else class="env-status">
        <span>当前生效环境：</span>
        <a-tag v-if="list.active_env" color="green">{{ list.active_env }}</a-tag>
        <a-tag v-else>未设置</a-tag>
        <a-button type="link" size="small" @click="selectActiveFile">查看/编辑当前 .env</a-button>
        <span class="env-root">项目目录：{{ list.project_root }}</span>
      </div>

      <a-alert
        v-if="list.duplicated && list.duplicated.length > 1"
        type="info"
        show-icon
        class="env-alert"
        :message="`有 ${list.duplicated.length} 个环境内容完全相同：${list.duplicated.join('、')}`"
      />

      <a-row :gutter="16" class="env-body">
        <!-- 左侧：环境列表 -->
        <a-col :span="8">
          <div class="env-side-head">
            <span>环境（{{ list.items.length }}）</span>
            <a-space>
              <a-button
                type="link"
                size="small"
                v-permission="'project:env:create'"
                @click="openCreate"
              >新建</a-button>
              <a-button
                type="link"
                size="small"
                v-permission="'project:env:create'"
                @click="triggerUpload"
              >上传</a-button>
            </a-space>
          </div>
          <input
            ref="uploadInput"
            type="file"
            accept=".env,.txt"
            style="display: none"
            @change="onUploadChange"
          />
          <div class="env-list">
            <div
              v-for="item in list.items"
              :key="item.name"
              class="env-item"
              :class="{ active: item.name === currentName }"
              @click="selectEnv(item)"
            >
              <div class="env-item-title">
                <a-tag v-if="item.is_active" color="green">生效</a-tag>
                <span class="env-item-name">{{ item.name }}</span>
                <a-tag v-if="item.external" color="orange">外部</a-tag>
              </div>
              <div class="env-item-meta">
                {{ item.key_count }} 项 · {{ formatSize(item.size) }}
                <template v-if="item.remark"> · {{ item.remark }}</template>
              </div>
            </div>
            <a-empty v-if="!list.items.length" description="还没有环境快照" />
          </div>
        </a-col>

        <!-- 右侧：内容编辑 -->
        <a-col :span="16">
          <template v-if="currentName">
            <div class="env-editor-head">
              <a-space wrap>
                <a-tag v-if="detail.is_active" color="green">当前生效</a-tag>
                <strong>{{ displayName }}</strong>
                <a-input
                  v-model:value="remark"
                  size="small"
                  style="width: 200px"
                  placeholder="备注（选填）"
                  :disabled="isActiveFile"
                />
              </a-space>
              <a-radio-group v-model:value="mode" size="small" button-style="solid">
                <a-radio-button value="table">表格</a-radio-button>
                <a-radio-button value="text">原文</a-radio-button>
              </a-radio-group>
            </div>

            <template v-if="mode === 'table'">
              <a-table
                :columns="kvColumns"
                :data-source="kvRows"
                :pagination="false"
                row-key="no"
                size="small"
                class="env-table"
                :scroll="TABLE_SCROLL_MODAL(kvColumns)"
                table-layout="fixed"
              >
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'key'">{{ record.key }}</template>
                  <template v-if="column.key === 'value'">
                    <a-input-password
                      v-if="record.sensitive"
                      :value="record.value"
                      @change="e => onValueChange(record, e.target.value)"
                    />
                    <a-input
                      v-else
                      :value="record.value"
                      @change="e => onValueChange(record, e.target.value)"
                    />
                  </template>
                  <template v-if="column.key === 'op'">
                    <a-button type="link" size="small" danger @click="removeRow(record)">
                      删除
                    </a-button>
                  </template>
                </template>
              </a-table>
              <a-button type="dashed" size="small" block @click="addVarOpen = true">
                + 新增变量
              </a-button>
            </template>
            <a-textarea
              v-else
              v-model:value="content"
              :rows="18"
              class="env-textarea"
              placeholder="每行 KEY=VALUE，# 开头的行作为注释保留"
            />

            <a-alert
              v-if="warnings.length"
              type="warning"
              show-icon
              class="env-warn"
              :message="`有 ${warnings.length} 行不是标准 KEY=VALUE 格式（已按原文保留）`"
              :description="warnings.join('；')"
            />

            <div class="env-actions">
              <a-button
                type="primary"
                :loading="saving"
                v-permission="'project:env:update'"
                @click="handleSave"
              >保存{{ dirty ? ' *' : '' }}</a-button>
              <a-button v-permission="'project:env:create'" @click="openSaveAs">另存为…</a-button>
              <a-button
                v-if="!isActiveFile"
                v-permission="'project:env:apply'"
                @click="handleApply"
              >应用此环境</a-button>
              <a-button
                v-if="!isActiveFile"
                v-permission="'project:env:update'"
                @click="renameOpen = true"
              >重命名</a-button>
              <a-button v-if="!isActiveFile" @click="handleDownload">下载</a-button>
              <a-popconfirm
                v-if="!isActiveFile"
                title="确定删除该环境？"
                @confirm="handleDelete"
              >
                <a-button danger v-permission="'project:env:delete'">删除</a-button>
              </a-popconfirm>
            </div>
          </template>
          <a-empty v-else description="请选择左侧环境，或查看当前生效的 .env" />
        </a-col>
      </a-row>
    </a-spin>

    <!-- 新建 / 另存为 -->
    <a-modal
      v-model:open="createOpen"
      :title="createForm.isSaveAs ? '另存为新环境' : '新建环境'"
      :confirm-loading="createLoading"
      @ok="handleCreate"
    >
      <a-form :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }">
        <a-form-item label="环境名" required>
          <a-input
            v-model:value="createForm.name"
            placeholder="字母/数字/下划线/中划线，如 test-huadong"
          />
        </a-form-item>
        <a-form-item v-if="!createForm.isSaveAs" label="内容来源">
          <a-radio-group v-model:value="createForm.source">
            <a-radio value="active">复制当前 .env</a-radio>
            <a-radio value="empty">空白</a-radio>
            <a-radio value="content">粘贴内容</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item v-if="createForm.isSaveAs || createForm.source === 'content'" label="内容">
          <a-textarea v-model:value="createForm.content" :rows="10" />
        </a-form-item>
        <a-form-item label="备注">
          <a-input v-model:value="createForm.remark" placeholder="选填" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 重命名 -->
    <a-modal
      v-model:open="renameOpen"
      title="重命名环境"
      :confirm-loading="renameLoading"
      @ok="handleRename"
    >
      <a-form :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }">
        <a-form-item label="新环境名" required>
          <a-input v-model:value="renameValue" placeholder="字母/数字/下划线/中划线" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 新增变量 -->
    <a-modal v-model:open="addVarOpen" title="新增变量" @ok="handleAddVar">
      <a-form :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }">
        <a-form-item label="键名" required>
          <a-input v-model:value="addVarKey" placeholder="如 MQTT_HOST" />
        </a-form-item>
        <a-form-item label="值">
          <a-input v-model:value="addVarValue" placeholder="选填" />
        </a-form-item>
      </a-form>
    </a-modal>
  </a-drawer>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import {
  getProjectEnvs,
  getProjectEnv,
  getProjectActiveEnv,
  createProjectEnv,
  uploadProjectEnv,
  saveProjectEnv,
  saveProjectActiveEnv,
  applyProjectEnv,
  renameProjectEnv,
  deleteProjectEnv,
  diffProjectEnvs,
  downloadProjectEnv
} from '@/api/projectEnv'
import { TABLE_SCROLL_MODAL } from '@/utils/tableScroll'

const props = defineProps({
  open: { type: Boolean, default: false },
  project: { type: Object, default: null }
})
const emit = defineEmits(['update:open'])

const ACTIVE_KEY = '@active'
const ENV_NAME_RE = /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/
const KV_RE = /^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/
const SENSITIVE_RE = /(?:^|_)(PASSWORD|PASSWD|PWD|SECRET|TOKEN|KEY|CREDENTIALS?)(?:_|$)/i

const loading = ref(false)
const saving = ref(false)
const list = ref({ project_root: '', has_active_env_file: false, active_env: null, drifted: false, duplicated: [], items: [] })
const currentName = ref('')
const isActiveFile = computed(() => currentName.value === ACTIVE_KEY)
const displayName = computed(() => (isActiveFile.value ? '当前生效 .env' : currentName.value))
const detail = ref({ lines: [], warnings: [], is_active: false })
const content = ref('')
const originalContent = ref('')
const remark = ref('')
const mode = ref('table')
const dirty = computed(() => content.value !== originalContent.value)

const projectId = computed(() => props.project?.id)

// ---------- 行解析（与后端 parse_env_lines 保持一致） ----------
function splitLines(text) {
  return String(text ?? '').replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n')
}

function parseLines(text) {
  const arr = splitLines(text)
  if (arr.length && arr[arr.length - 1] === '') arr.pop()
  return arr.map((raw, i) => {
    const no = i + 1
    const stripped = raw.trim()
    if (!stripped) return { no, type: 'blank', raw }
    if (stripped.startsWith('#') || stripped.startsWith(';')) return { no, type: 'comment', raw }
    const m = KV_RE.exec(raw)
    if (m) {
      return {
        no,
        type: 'kv',
        raw,
        key: m[1],
        value: m[2],
        sensitive: SENSITIVE_RE.test(m[1])
      }
    }
    return { no, type: 'raw', raw }
  })
}

const parsed = computed(() => parseLines(content.value))
const kvRows = computed(() => parsed.value.filter(l => l.type === 'kv'))
const warnings = computed(() =>
  parsed.value
    .filter(l => l.type === 'raw')
    .map(l => `第 ${l.no} 行不是标准 KEY=VALUE 格式，已按原文保留`)
)

const kvColumns = [
  { title: '键', key: 'key', dataIndex: 'key', width: '38%' },
  { title: '值', key: 'value', dataIndex: 'value' },
  { title: '操作', key: 'op', width: 80 }
]

function setLine(no, text) {
  const arr = splitLines(content.value)
  arr[no - 1] = text
  content.value = arr.join('\n')
}

function onValueChange(record, val) {
  const exportPrefix = /^\s*export\s+/i.test(record.raw) ? 'export ' : ''
  setLine(record.no, `${exportPrefix}${record.key}=${val}`)
}

function removeRow(record) {
  const arr = splitLines(content.value)
  arr.splice(record.no - 1, 1)
  content.value = arr.join('\n')
}

function formatSize(bytes) {
  const size = Number(bytes) || 0
  if (size < 1024) return `${size}B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)}KB`
  return `${(size / 1024 / 1024).toFixed(1)}MB`
}

// ---------- 数据加载 ----------
async function loadList() {
  if (!projectId.value) return
  loading.value = true
  try {
    const res = await getProjectEnvs(projectId.value)
    list.value = res.data || list.value
  } catch (e) {
    // 错误已由拦截器提示
  } finally {
    loading.value = false
  }
}

function applyDetail(data) {
  detail.value = data || {}
  content.value = data?.content || ''
  originalContent.value = content.value
  remark.value = data?.remark || ''
}

async function loadDetail(name) {
  if (!projectId.value || !name) return
  loading.value = true
  try {
    const res = name === ACTIVE_KEY
      ? await getProjectActiveEnv(projectId.value)
      : await getProjectEnv(projectId.value, name)
    applyDetail(res.data)
  } catch (e) {
    content.value = ''
    originalContent.value = ''
  } finally {
    loading.value = false
  }
}

async function selectEnv(item) {
  if (item.name === currentName.value) return
  if (!(await confirmDiscard())) return
  currentName.value = item.name
  await loadDetail(item.name)
}

async function selectActiveFile() {
  if (currentName.value === ACTIVE_KEY) return
  if (!(await confirmDiscard())) return
  currentName.value = ACTIVE_KEY
  await loadDetail(ACTIVE_KEY)
}

function confirmDiscard() {
  if (!dirty.value) return Promise.resolve(true)
  return new Promise(resolve => {
    Modal.confirm({
      title: '当前修改尚未保存',
      content: '切换后将丢失未保存的修改，是否继续？',
      okText: '继续',
      okType: 'danger',
      cancelText: '取消',
      onOk: () => resolve(true),
      onCancel: () => resolve(false)
    })
  })
}

async function refreshAfterWrite(keepCurrent) {
  await loadList()
  if (!projectId.value) return
  if (keepCurrent && currentName.value === ACTIVE_KEY) {
    await loadDetail(ACTIVE_KEY)
  } else if (currentName.value) {
    await loadDetail(currentName.value)
  }
}

const uploadInput = ref(null)
const createOpen = ref(false)
const createLoading = ref(false)
const createForm = reactive({ isSaveAs: false, name: '', source: 'active', content: '', remark: '' })
const renameOpen = ref(false)
const renameLoading = ref(false)
const renameValue = ref('')
const addVarOpen = ref(false)
const addVarKey = ref('')
const addVarValue = ref('')

function openCreate() {
  createForm.isSaveAs = false
  createForm.name = ''
  createForm.source = list.value.has_active_env_file ? 'active' : 'empty'
  createForm.content = content.value
  createForm.remark = ''
  createOpen.value = true
}

function openSaveAs() {
  createForm.isSaveAs = true
  createForm.name = ''
  createForm.source = 'content'
  createForm.content = content.value
  createForm.remark = remark.value
  createOpen.value = true
}

async function handleCreate() {
  const name = (createForm.name || '').trim()
  if (!ENV_NAME_RE.test(name)) {
    message.warning('环境名不合法：仅允许字母、数字、下划线、中划线')
    return
  }
  createLoading.value = true
  try {
    if (createForm.isSaveAs) {
      await createProjectEnv(projectId.value, {
        name,
        source: 'content',
        content: content.value,
        remark: createForm.remark || null
      })
    } else {
      await createProjectEnv(projectId.value, {
        name,
        source: createForm.source,
        content: createForm.source === 'content' ? createForm.content : null,
        remark: createForm.remark || null
      })
    }
    createOpen.value = false
    message.success(`环境 ${name} 已创建`)
    await loadList()
    if (!currentName.value) {
      currentName.value = name
      await loadDetail(name)
    }
  } catch (e) {
    // 错误已由拦截器提示
  } finally {
    createLoading.value = false
  }
}

function triggerUpload() {
  uploadInput.value?.click()
}

async function onUploadChange(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file || !projectId.value) return
  const text = await file.text()
  try {
    const res = await uploadProjectEnv(projectId.value, {
      filename: file.name,
      content: text,
      remark: null
    })
    message.success(`环境 ${res.data?.name || ''} 已上传`)
    await loadList()
  } catch (e) {
    // 错误已由拦截器提示
  }
}

async function handleSave() {
  if (!currentName.value) return
  saving.value = true
  try {
    if (isActiveFile.value) {
      await saveProjectActiveEnv(projectId.value, { content: content.value })
    } else {
      await saveProjectEnv(projectId.value, currentName.value, {
        content: content.value,
        remark: remark.value || null
      })
    }
    message.success('已保存')
    await refreshAfterWrite(true)
  } catch (e) {
    // 错误已由拦截器提示
  } finally {
    saving.value = false
  }
}

async function handleApply() {
  try {
    const res = await diffProjectEnvs(projectId.value, ACTIVE_KEY, currentName.value)
    const d = res.data || {}
    const summary = `新增 ${d.added?.length || 0} 项、修改 ${d.changed?.length || 0} 项、删除 ${d.removed?.length || 0} 项`
    Modal.confirm({
      title: `切换到环境 ${currentName.value}？`,
      content: `与当前 .env 相比：${summary}。切换会覆盖项目目录下的 .env，后续执行即使用该环境。`,
      okText: '确认切换',
      onOk: async () => {
        await applyProjectEnv(projectId.value, currentName.value)
        message.success(`已切换到环境 ${currentName.value}`)
        await refreshAfterWrite(false)
      }
    })
  } catch (e) {
    // 错误已由拦截器提示
  }
}

async function handleRename() {
  const newName = (renameValue.value || '').trim()
  if (!ENV_NAME_RE.test(newName)) {
    message.warning('环境名不合法：仅允许字母、数字、下划线、中划线')
    return
  }
  renameLoading.value = true
  try {
    const oldName = currentName.value
    await renameProjectEnv(projectId.value, oldName, newName)
    renameOpen.value = false
    message.success(`已重命名为 ${newName}`)
    currentName.value = newName
    await refreshAfterWrite(false)
  } catch (e) {
    // 错误已由拦截器提示
  } finally {
    renameLoading.value = false
  }
}

async function handleDelete() {
  try {
    await deleteProjectEnv(projectId.value, currentName.value)
    message.success('环境已删除')
    currentName.value = ''
    await loadList()
    const active = list.value.active_env
    if (active) {
      currentName.value = active
      await loadDetail(active)
    }
  } catch (e) {
    // 错误已由拦截器提示
  }
}

async function handleDownload() {
  try {
    const blob = await downloadProjectEnv(projectId.value, currentName.value)
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `${currentName.value}.env`
    link.click()
    URL.revokeObjectURL(link.href)
  } catch (e) {
    // 错误已由拦截器提示
  }
}

function handleAddVar() {
  const key = (addVarKey.value || '').trim()
  if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(key)) {
    message.warning('键名不合法：需以字母或下划线开头，仅含字母、数字、下划线')
    return
  }
  const body = splitLines(content.value)
  if (body.length && body[body.length - 1] !== '') body.push('')
  body.push(`${key}=${addVarValue.value ?? ''}`)
  content.value = body.join('\n')
  addVarOpen.value = false
  addVarKey.value = ''
  addVarValue.value = ''
}

watch(renameOpen, open => {
  if (open) renameValue.value = currentName.value
})

watch(
  () => props.open,
  async open => {
    if (!open) return
    currentName.value = ''
    content.value = ''
    originalContent.value = ''
    mode.value = 'table'
    await loadList()
    const target = list.value.active_env || list.value.items[0]?.name
    if (target) {
      currentName.value = target
      await loadDetail(target)
    }
  }
)

async function handleClose() {
  if (!(await confirmDiscard())) return
  emit('update:open', false)
}
</script>

<style scoped>
.env-alert {
  margin-bottom: 12px;
}

.env-status {
  margin-bottom: 12px;
  color: rgba(0, 0, 0, 0.65);
}

.env-root {
  margin-left: 12px;
  color: rgba(0, 0, 0, 0.45);
  font-size: 12px;
}

.env-body {
  margin-top: 8px;
}

.env-side-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-weight: 500;
}

.env-list {
  max-height: 560px;
  overflow-y: auto;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  padding: 4px;
}

.env-item {
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
}

.env-item:hover {
  background: #fafafa;
}

.env-item.active {
  background: #e6f4ff;
}

.env-item-title {
  display: flex;
  align-items: center;
  gap: 6px;
}

.env-item-name {
  font-weight: 500;
  word-break: break-all;
}

.env-item-meta {
  margin-top: 2px;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
}

.env-editor-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  gap: 12px;
}

.env-table {
  margin-bottom: 8px;
}

.env-textarea {
  font-family: Consolas, Monaco, monospace;
  margin-bottom: 8px;
}

.env-warn {
  margin: 8px 0;
}

.env-actions {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
