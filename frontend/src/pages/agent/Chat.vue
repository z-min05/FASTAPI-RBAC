<template>
  <div class="agent-chat">
    <!-- 左侧：会话列表 -->
    <div class="agent-side">
      <div class="side-head">
        <span class="side-title">会话列表</span>
        <a-button type="primary" size="small" :loading="creating" @click="openCreate">
          <PlusOutlined /> 新建对话
        </a-button>
      </div>

      <div class="side-list">
        <div
          v-for="conv in conversations"
          :key="conv.id"
          class="conv-item"
          :class="{ active: conv.id === currentId }"
          @click="handleSelect(conv)"
        >
          <div class="conv-main">
            <div class="conv-title">{{ conv.title }}</div>
            <div class="conv-time">{{ formatTime(conv.updated_at) }}</div>
          </div>
          <DeleteOutlined
            v-if="conv.id === currentId"
            class="conv-del"
            @click.stop="handleDelete(conv)"
          />
        </div>
        <div v-if="!loadingConvs && !conversations.length" class="side-empty">
          暂无会话，点击右上角新建
        </div>
      </div>
    </div>

    <!-- 右侧：聊天区 -->
    <div class="agent-main">
      <template v-if="currentId">
        <div class="chat-head">
          <div class="chat-head-left">
            <span class="chat-title">{{ currentTitle }}</span>
            <a-tag v-if="currentAgentName" color="blue" class="agent-tag">{{ currentAgentName }}</a-tag>
          </div>
          <a-tooltip v-if="modelTip" :title="modelTip">
            <span class="chat-model">{{ currentModel }}</span>
          </a-tooltip>
        </div>

        <div class="chat-body" ref="bodyRef">
          <a-spin :spinning="loadingMessages">
            <div v-for="msg in messages" :key="msg.key" class="msg-row" :class="msg.role">
              <div class="msg-avatar" :class="msg.role">{{ msg.role === 'user' ? '我' : 'AI' }}</div>
              <div class="msg-content">
                <!-- 工具调用：默认折叠、可展开（置于文本上方，符合“先调工具后出结果”的语义） -->
                <div v-if="msg.tools && msg.tools.length" class="msg-tools">
                  <div class="tools-toggle" @click="msg.toolsOpen = !msg.toolsOpen">
                    <LoadingOutlined v-if="msg.tools.some(t => !t.done)" class="tools-icon spin" />
                    <ToolOutlined v-else class="tools-icon" />
                    <span class="tools-text">{{ toolsLabel(msg) }}</span>
                    <DownOutlined v-if="msg.toolsOpen" class="tools-caret" />
                    <RightOutlined v-else class="tools-caret" />
                  </div>
                  <div v-if="msg.toolsOpen" class="tools-list">
                    <div v-for="t in msg.tools" :key="t.call_id || t.index" class="tool-item">
                      <div class="tool-item-head">
                        <code class="tool-name">{{ t.name }}</code>
                        <span class="tool-status" :class="{ ok: t.done }">{{ t.done ? '完成' : '运行中' }}</span>
                      </div>
                      <pre v-if="t.argsText" class="tool-pre">{{ t.argsText }}</pre>
                      <pre v-if="t.done && t.output" class="tool-pre">{{ t.output }}</pre>
                    </div>
                  </div>
                </div>

                <div v-if="msg.content || msg.error || (msg.streaming && !(msg.tools && msg.tools.length))" class="msg-bubble">
                  <template v-if="msg.content">{{ msg.content }}</template>
                  <span v-else-if="msg.error" class="err-text">{{ msg.errorText || '抱歉，请求失败，请稍后重试。' }}</span>
                  <span v-else class="thinking">思考中…</span>
                </div>

                <div class="msg-meta">
                  <span v-if="msg.error && msg.content" class="meta-err">{{ msg.errorText || '请求失败' }}</span>
                  <template v-else-if="msg.role === 'assistant'">
                    <span v-if="msg.tokens && msg.tokens.total != null">
                      输入 {{ msg.tokens.input }} · 输出 {{ msg.tokens.output }} · 合计 {{ msg.tokens.total }}
                    </span>
                    <span v-else-if="msg.token_total != null">tokens: {{ msg.token_total }}</span>
                  </template>
                </div>
              </div>
            </div>
            <div v-if="!loadingMessages && !messages.length" class="chat-body-empty">
              <RobotOutlined />
              <p>开始新的对话吧，发送第一条消息</p>
            </div>
          </a-spin>
        </div>

        <div class="chat-input">
          <a-textarea
            ref="inputRef"
            v-model:value="inputText"
            :rows="3"
            :disabled="sending"
            placeholder="输入消息，Enter 发送，Shift + Enter 换行"
            @keydown="handleKeydown"
            @compositionend="handleCompositionEnd"
            @input="handleInput"
          />
          <div class="input-actions">
            <span class="input-hint">AI 生成内容仅供参考</span>
            <a-button type="primary" :loading="sending" :disabled="!inputText.trim()" @click="handleSend">
              <SendOutlined /> 发送
            </a-button>
          </div>
        </div>
      </template>

      <div v-else class="chat-empty">
        <RobotOutlined />
        <p class="empty-title">AI 助手</p>
        <p class="empty-sub">选择左侧会话，或点击“新建对话”开始</p>
      </div>
    </div>

    <!-- 选择 Agent 开始新对话 -->
    <a-modal v-model:open="createVisible" title="选择 Agent 开始对话" :footer="null" width="420" wrap-class-name="create-conv-modal">
      <div v-if="agents.length" class="agent-picker">
        <div
          v-for="ag in agents"
          :key="ag.id"
          class="agent-card"
          :class="{ disabled: ag.enabled === false }"
          @click="pickAgent(ag)"
        >
          <div class="agent-card-head">
            <span class="agent-card-name">{{ ag.name }}</span>
            <a-tag color="blue">{{ ag.llm_model || '未绑定模型' }}</a-tag>
          </div>
          <div v-if="ag.description" class="agent-card-desc">{{ ag.description }}</div>
          <div class="agent-card-meta">
            <a-tag v-for="t in ag.tools || []" :key="t" color="green">{{ t }}</a-tag>
            <a-tag v-if="ag.enabled === false" color="red">已停用</a-tag>
          </div>
        </div>
      </div>
      <div v-else class="agent-empty">
        你还没有 Agent，请先
        <a @click="goManage">去创建 Agent</a>
        再开始对话
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted } from 'vue'
import { Modal, message } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import {
  PlusOutlined, DeleteOutlined, SendOutlined, RobotOutlined,
  DownOutlined, RightOutlined, ToolOutlined, LoadingOutlined
} from '@ant-design/icons-vue'
import {
  listAgentConversations,
  createAgentConversation,
  deleteAgentConversation,
  listAgentMessages,
  sendAgentMessageStream,
  listAgents
} from '@/api/agent'

const router = useRouter()

// ---------------- 状态 ----------------
const conversations = ref([])
const loadingConvs = ref(false)
const currentId = ref(null)
const messages = ref([])
const loadingMessages = ref(false)
const inputText = ref('')
const sending = ref(false)
const creating = ref(false)
const inputRef = ref(null)
// 中文输入法下 Enter 处于组合态时先挂起，compositionend 后自动补发
let pendingCompositionSend = false
// 发送后的“清空保护”：输入法在 compositionend 后可能把已发文本回写 input/model，
// 短窗口内若检测到同样的文本再次出现则强制清掉
let sentText = ''
let clearGuardUntil = 0

const agents = ref([])
const createVisible = ref(false)
const bodyRef = ref(null)

// ---------------- 计算属性 ----------------
const currentConv = computed(() => conversations.value.find(c => c.id === currentId.value) || null)
const currentTitle = computed(() => currentConv.value?.title || '新对话')
const currentModel = computed(() => currentConv.value?.model || '')
const modelTip = computed(() => (currentModel.value ? `模型：${currentModel.value}` : ''))
const currentAgentName = computed(() => currentConv.value?.agent_name || '')

// ---------------- 会话 ----------------
async function loadConversations() {
  loadingConvs.value = true
  try {
    const res = await listAgentConversations({ page: 1, page_size: 100 })
    conversations.value = res.data?.items || []
    // 若当前会话已不在列表（被删除/归档），回到空状态
    if (currentId.value && !conversations.value.find(c => c.id === currentId.value)) {
      currentId.value = null
      messages.value = []
    }
  } catch (e) {
    // 错误已由拦截器提示
  } finally {
    loadingConvs.value = false
  }
}

function openCreate() {
  if (!agents.value.length) {
    message.warning('请先创建 Agent，再开始对话')
    goManage()
    return
  }
  createVisible.value = true
}

function pickAgent(agent) {
  if (agent.enabled === false) {
    message.warning('该 Agent 已停用，请先在「我的 Agent」中启用')
    return
  }
  createVisible.value = false
  createWithAgent(agent.id)
}

async function createWithAgent(agentId) {
  if (creating.value) return
  creating.value = true
  try {
    const res = await createAgentConversation({ agent_id: agentId })
    const conv = res.data
    conversations.value.unshift(conv)
    await handleSelect(conv)
    loadConversations()
  } catch (e) {
    // 错误已提示
  } finally {
    creating.value = false
  }
}

function goManage() {
  router.push('/agent/manage')
}

async function handleSelect(conv) {
  if (conv.id === currentId.value) return
  currentId.value = conv.id
  inputText.value = ''
  await loadMessages(conv.id)
}

function handleDelete(conv) {
  Modal.confirm({
    title: '删除会话',
    content: `确定删除会话「${conv.title}」吗？该操作不可恢复。`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    async onOk() {
      await deleteAgentConversation(conv.id)
      message.success('删除成功')
      if (currentId.value === conv.id) {
        currentId.value = null
        messages.value = []
      }
      loadConversations()
    }
  })
}

// ---------------- 消息 ----------------
async function loadMessages(convId) {
  loadingMessages.value = true
  messages.value = []
  try {
    const res = await listAgentMessages(convId, { page: 1, page_size: 100 })
    messages.value = (res.data?.items || []).map(m => ({ ...m, key: `s-${m.id}` }))
    await scrollToBottom()
  } catch (e) {
    // 错误已提示
  } finally {
    loadingMessages.value = false
  }
}

let scrollRaf = 0
function scheduleScroll() {
  if (scrollRaf) return
  scrollRaf = requestAnimationFrame(() => {
    scrollRaf = 0
    scrollToBottom()
  })
}

function formatToolArgs(args) {
  if (typeof args === 'string') return args
  try {
    return JSON.stringify(args, null, 2)
  } catch (e) {
    return String(args)
  }
}

function toolsLabel(msg) {
  const running = msg.tools.some(t => !t.done)
  return running ? '正在调用工具…' : `使用了 ${msg.tools.length} 次工具调用`
}

async function handleSend() {
  const content = inputText.value.trim()
  if (!content || sending.value || !currentId.value) return

  clearInputBox(content)
  const ts = Date.now()
  const aiKey = `a-${ts}`
  messages.value.push({ key: `u-${ts}`, role: 'user', content })
  messages.value.push({
    key: aiKey,
    role: 'assistant',
    content: '',
    streaming: true,
    error: false,
    errorText: '',
    tools: [],
    toolsOpen: false,
    tokens: null
  })
  sending.value = true
  await scrollToBottom()

  const toolMap = new Map()

  // SSE 事件队列：本地/短响应时整个 body 可能一次网络读取就全部到达，
  // 若同步处理会把全部文本一次性渲染（看起来不像流式）。
  // 改为固定间隔逐条消费，保证“打字机”式的增量呈现。
  const queue = []
  let busy = false

  function applyEvent(ev) {
    const idx = messages.value.findIndex(m => m.key === aiKey)
    if (idx < 0) return
    const msg = messages.value[idx]
    switch (ev.type) {
      case 'text':
        msg.content += ev.content || ''
        scheduleScroll()
        break
      case 'tool': {
        const tool = {
          index: ev.index,
          call_id: ev.call_id,
          name: ev.name || '未知工具',
          argsText: formatToolArgs(ev.args),
          output: '',
          done: false
        }
        msg.tools.push(tool)
        if (ev.call_id) toolMap.set(ev.call_id, tool)
        scheduleScroll()
        break
      }
      case 'tool_result': {
        const tool = toolMap.get(ev.call_id) ||
          msg.tools.find(t => t.index === ev.index) ||
          msg.tools.find(t => !t.done)
        if (tool) {
          tool.output = ev.output || ''
          tool.done = true
        }
        scheduleScroll()
        break
      }
      case 'done':
        msg.streaming = false
        msg.content = msg.content || ev.reply || ''
        if (ev.tokens) msg.tokens = ev.tokens
        break
      case 'error':
        msg.streaming = false
        msg.error = true
        msg.errorText = ev.message || '抱歉，请求失败，请稍后重试。'
        break
    }
  }

  async function pump() {
    if (busy) return
    busy = true
    while (queue.length) {
      applyEvent(queue.shift())
      // 每条事件间的小间隔：既保证逐字呈现，也不影响真实网络的到达节奏
      await new Promise(r => setTimeout(r, 8))
    }
    busy = false
  }

  async function drainQueue() {
    while (queue.length || busy) {
      await new Promise(r => setTimeout(r, 10))
    }
  }

  function enqueueEvent(ev) {
    // 供应商可能一次返回较长文本片段，拆成小段以保证平滑的“打字机”效果
    if (ev.type === 'text' && ev.content && ev.content.length > 8) {
      for (let i = 0; i < ev.content.length; i += 8) {
        queue.push({ type: 'text', content: ev.content.slice(i, i + 8) })
      }
      pump()
      return
    }
    queue.push(ev)
    pump()
  }

  try {
    await sendAgentMessageStream(currentId.value, content, {
      onEvent(ev) {
        enqueueEvent(ev)
      }
    })
    await drainQueue() // 网络结束前保证队列消费完（含 done 事件）
    await scrollToBottom()
  } catch (e) {
    const idx = messages.value.findIndex(m => m.key === aiKey)
    if (idx >= 0) {
      const msg = messages.value[idx]
      msg.streaming = false
      msg.error = true
      msg.errorText = e?.message || '抱歉，请求失败，请稍后重试。'
    }
  } finally {
    sending.value = false
    loadConversations() // 刷新标题/排序（首次对话自动命名后）
    await scrollToBottom()
  }
}

function clearInputBox(content) {
  inputText.value = ''
  sentText = content
  clearGuardUntil = Date.now() + 300
  // 输入法 compositionend 之后可能还会把文本写回 textarea（宏任务），
  // 下一个宏任务里再强制清一次 DOM，确保视觉上真正清空
  window.setTimeout(() => {
    const inst = inputRef.value
    const el = (inst && (inst.resizableTextArea?.textArea || inst.textArea)) || inst
    if (el && typeof el.value === 'string' && el.value === sentText) el.value = ''
    if (Date.now() < clearGuardUntil && inputText.value === sentText) inputText.value = ''
  }, 0)
}

function handleInput() {
  // 输入法尾部回写：把“刚发送的文本”重新写回时，直接清掉
  if (Date.now() < clearGuardUntil && inputText.value === sentText) {
    inputText.value = ''
  }
}

function handleKeydown(e) {
  if (e.key !== 'Enter' || e.shiftKey) return
  const composing = e.isComposing || e.keyCode === 229
  if (!composing) {
    e.preventDefault()
    handleSend()
    return
  }
  // 组合输入中按 Enter：用于确认候选词。这里不能 preventDefault（会阻止输入法
  // 提交、导致 compositionend 不触发），标记后等提交完成再发送。
  pendingCompositionSend = true
  // 兜底：个别输入法/浏览器提交后不派发 compositionend；
  // 文本已同步进 model 才发送，否则放弃挂起（避免误发空内容/旧内容）
  window.setTimeout(() => {
    if (!pendingCompositionSend) return
    pendingCompositionSend = false
    if (inputText.value.trim()) {
      handleSend()
    }
  }, 600)
}

function handleCompositionEnd() {
  if (!pendingCompositionSend) return
  pendingCompositionSend = false
  // 等输入法把最终文本同步到 model 后再发送，确保发的是完整内容且发后清空生效
  nextTick(() => handleSend())
}

async function scrollToBottom() {
  await nextTick()
  if (bodyRef.value) {
    bodyRef.value.scrollTop = bodyRef.value.scrollHeight
  }
}

// ---------------- Agent 元数据 ----------------
async function loadMeta() {
  try {
    const agentsRes = await listAgents({ page: 1, page_size: 100 })
    agents.value = agentsRes.data?.items || []
  } catch (e) {
    // 功能开关未启用等情况，忽略元数据加载失败
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

// ---------------- 初始化 ----------------
onMounted(async () => {
  loadMeta()
  loadConversations()
})
</script>

<style scoped>
.agent-chat {
  display: flex;
  height: calc(100vh - 170px);
  min-height: 480px;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  overflow: hidden;
}

/* ===== 左侧会话列表 ===== */
.agent-side {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: #fafafa;
  border-right: 1px solid #f0f0f0;
}

.side-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  border-bottom: 1px solid #f0f0f0;
}

.side-title {
  font-weight: 600;
  font-size: 14px;
}

.side-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.conv-item {
  display: flex;
  align-items: center;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 4px;
}

.conv-item:hover {
  background: rgba(0, 0, 0, 0.04);
}

.conv-item.active {
  background: #e6f4ff;
}

.conv-main {
  flex: 1;
  min-width: 0;
}

.conv-title {
  font-size: 13px;
  color: rgba(0, 0, 0, 0.88);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-time {
  font-size: 12px;
  color: #999;
  margin-top: 2px;
}

.conv-del {
  color: #999;
  padding: 4px;
}

.conv-del:hover {
  color: #ff4d4f;
}

.side-empty {
  text-align: center;
  color: #999;
  font-size: 13px;
  padding: 32px 0;
}

/* ===== 右侧聊天区 ===== */
.agent-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: #fff;
}

.chat-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  border-bottom: 1px solid #f0f0f0;
}

.chat-head-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.chat-title {
  font-weight: 600;
  font-size: 15px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-tag {
  flex-shrink: 0;
}

.chat-model {
  font-size: 12px;
  color: #999;
  cursor: default;
}

.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: #f7f9fc;
}

.chat-body-empty {
  text-align: center;
  color: #bbb;
  padding-top: 120px;
  font-size: 18px;
}

.chat-body-empty p {
  color: #999;
  font-size: 13px;
  margin-top: 8px;
}

.msg-row {
  display: flex;
  margin-bottom: 16px;
}

.msg-row.user {
  flex-direction: row-reverse;
}

.msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: #fff;
  flex-shrink: 0;
  margin: 0 10px;
}

.msg-avatar.user {
  background: #1677ff;
}

.msg-avatar.assistant {
  background: #722ed1;
}

.msg-content {
  max-width: 70%;
  min-width: 0;
}

.msg-row.user .msg-content {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.msg-bubble {
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  background: #fff;
  border: 1px solid #f0f0f0;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}

.msg-row.user .msg-bubble {
  background: #1677ff;
  color: #fff;
  border-color: #1677ff;
}

.msg-meta {
  font-size: 12px;
  color: #bbb;
  margin-top: 4px;
}

.msg-row.user .msg-meta {
  color: rgba(255, 255, 255, 0.65);
}

/* ===== 流式气泡 / 工具调用 / Token 展示 ===== */
.thinking {
  color: #aaa;
}

.err-text,
.meta-err {
  color: #ff4d4f;
}

.msg-tools {
  margin-top: 6px;
  font-size: 12px;
}

.msg-tools + .msg-bubble {
  margin-top: 8px;
}

.tools-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 6px;
  color: #8c8c8c;
  background: rgba(0, 0, 0, 0.03);
  cursor: pointer;
  user-select: none;
  line-height: 20px;
  transition: background 0.2s;
}

.tools-toggle:hover {
  color: #595959;
  background: rgba(0, 0, 0, 0.06);
}

.tools-icon {
  font-size: 12px;
}

.tools-icon.spin {
  animation: tools-spin 1s linear infinite;
}

@keyframes tools-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.tools-caret {
  font-size: 10px;
}

.tools-list {
  margin-top: 6px;
  padding: 6px 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 320px;
  overflow-y: auto;
  background: rgba(0, 0, 0, 0.02);
  border: 1px solid #f0f0f0;
  border-radius: 6px;
}

.tool-item {
  font-size: 12px;
}

.tool-item-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tool-name {
  font-size: 12px;
  color: #595959;
  background: rgba(0, 0, 0, 0.06);
  padding: 1px 6px;
  border-radius: 4px;
}

.tool-status {
  color: #aaa;
}

.tool-status.ok {
  color: #52c41a;
}

.tool-pre {
  margin: 4px 0 0;
  padding: 6px 8px;
  border-radius: 4px;
  background: #fff;
  border: 1px solid #f0f0f0;
  font-size: 12px;
  line-height: 1.5;
  color: #595959;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow: auto;
}

/* ===== 输入区 ===== */
.chat-input {
  padding: 12px 16px;
  border-top: 1px solid #f0f0f0;
}

.input-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}

.input-hint {
  font-size: 12px;
  color: #bbb;
}

/* ===== 空状态 ===== */
.chat-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #d9d9d9;
  font-size: 56px;
}

.empty-title {
  font-size: 20px;
  color: rgba(0, 0, 0, 0.88);
  margin: 12px 0 4px;
}

.empty-sub {
  font-size: 13px;
  color: #999;
  margin-bottom: 12px;
}

/* ===== Agent 选择弹窗 ===== */
.agent-picker {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.agent-card {
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  padding: 10px 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.agent-card:hover {
  border-color: #1677ff;
  background: #f0f7ff;
}

.agent-card.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.agent-card-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.agent-card-name {
  font-weight: 600;
}

.agent-card-desc {
  margin-top: 4px;
  font-size: 12px;
  color: #666;
}

.agent-card-meta {
  margin-top: 6px;
}

.agent-empty {
  padding: 24px;
  text-align: center;
  color: #999;
}
</style>

<style>
/* 兜底强制限制“选择 Agent 开始对话”弹窗宽度（弹窗渲染在 body 下，需用全局非 scoped 样式） */
.create-conv-modal .ant-modal {
  width: 420px !important;
  max-width: calc(100vw - 24px);
}
</style>
