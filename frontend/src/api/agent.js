import request from './index'

// ==================== 会话 ====================

export function createAgentConversation(data) {
  return request.post('/agent/conversations', data)
}

export function listAgentConversations(params) {
  return request.get('/agent/conversations', { params })
}

export function getAgentConversation(id) {
  return request.get(`/agent/conversations/${id}`)
}

export function updateAgentConversation(id, data) {
  return request.put(`/agent/conversations/${id}`, data)
}

export function deleteAgentConversation(id) {
  return request.delete(`/agent/conversations/${id}`)
}

// ==================== 消息 ====================

export function listAgentMessages(conversationId, params) {
  return request.get(`/agent/conversations/${conversationId}/messages`, { params })
}

// AI 生成可能较慢，单独放宽超时时间
export function sendAgentMessage(conversationId, content) {
  return request.post(
    `/agent/conversations/${conversationId}/messages`,
    { content },
    { timeout: 180000 }
  )
}

// SSE 流式发送：onEvent({type, ...}) 逐事件回调；支持 AbortSignal 取消
export function sendAgentMessageStream(conversationId, content, { onEvent, signal } = {}) {
  const base = import.meta.env.VITE_API_BASE_URL || '/api/v1'
  const token = localStorage.getItem('access_token')
  return new Promise((resolve, reject) => {
    fetch(`${base}/agent/conversations/${conversationId}/messages/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      },
      body: JSON.stringify({ content }),
      signal
    })
      .then(async (resp) => {
        // 前置校验失败（409 快照变更、503 开关关闭等）返回的是普通 JSON 错误
        if (!resp.ok || !(resp.headers.get('content-type') || '').includes('text/event-stream')) {
          let errMsg = '请求失败'
          try {
            const body = await resp.json()
            errMsg = body?.detail || body?.message || errMsg
          } catch (e) {
            /* 非 JSON 错误体，忽略 */
          }
          const err = new Error(errMsg)
          err.status = resp.status
          throw err
        }
        const reader = resp.body.getReader()
        const decoder = new TextDecoder('utf-8')
        let buffer = ''

        const pump = () =>
          reader.read().then(({ done, value }) => {
            if (done) {
              resolve()
              return
            }
            buffer += decoder.decode(value, { stream: true })
            let idx
            while ((idx = buffer.indexOf('\n')) >= 0) {
              const line = buffer.slice(0, idx).trim()
              buffer = buffer.slice(idx + 1)
              if (line.startsWith('data:')) {
                const payload = line.slice(5).trim()
                if (payload) {
                  try {
                    if (onEvent) onEvent(JSON.parse(payload))
                  } catch (e) {
                    /* 忽略无法解析的行 */
                  }
                }
              }
            }
            return pump()
          })
        return pump()
      })
      .catch((err) => {
        if (err?.name === 'AbortError') {
          const e = new Error('已取消发送')
          e.aborted = true
          reject(e)
          return
        }
        reject(err)
      })
  })
}

// ==================== LLM 配置（平台级，超管维护） ====================

export function listLlmConfigs(params) {
  return request.get('/agent/llms', { params })
}

export function getLlmConfig(id) {
  return request.get(`/agent/llms/${id}`)
}

export function createLlmConfig(data) {
  return request.post('/agent/llms', data)
}

export function updateLlmConfig(id, data) {
  return request.put(`/agent/llms/${id}`, data)
}

export function deleteLlmConfig(id) {
  return request.delete(`/agent/llms/${id}`)
}

// ==================== Agent 定义（用户自建） ====================

export function listAgents(params) {
  return request.get('/agent/agents', { params })
}

export function getAgent(id) {
  return request.get(`/agent/agents/${id}`)
}

export function createAgent(data) {
  return request.post('/agent/agents', data)
}

export function updateAgent(id, data) {
  return request.put(`/agent/agents/${id}`, data)
}

export function deleteAgent(id) {
  return request.delete(`/agent/agents/${id}`)
}

// ==================== 能力 / 统计 ====================

export function getAgentTools() {
  return request.get('/agent/tools')
}

export function getAgentTokenStats(params) {
  return request.get('/agent/stats/tokens', { params })
}
