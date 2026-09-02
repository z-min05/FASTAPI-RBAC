<template>
  <div>
    <div class="page-header">
      <a-space>
        <a-input-search
          v-model:value="searchText"
          placeholder="搜索名称/模型"
          style="width: 240px"
          allow-clear
          @search="handleReset"
        />
        <a-select
          v-model:value="enabledFilter"
          placeholder="状态"
          style="width: 120px"
          allow-clear
          :options="enabledOptions"
          @change="handleReset"
        />
        <a-button @click="handleReset">重置</a-button>
        <a-button type="primary" @click="showModal()" v-permission="'agent:llm:create'">
          <PlusOutlined /> 新增 LLM
        </a-button>
      </a-space>
    </div>

    <a-table
      :columns="columns"
      :data-source="tableData"
      :loading="loading"
      :pagination="pagination"
      @change="handleTableChange"
      row-key="id"
      :scroll="{ x: 900 }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'provider'">
          {{ providerLabel(record.provider) }}
        </template>
        <template v-if="column.key === 'enabled'">
          <a-tag :color="record.enabled ? 'green' : 'red'">
            {{ record.enabled ? '启用' : '停用' }}
          </a-tag>
        </template>
        <template v-if="column.key === 'created_at'">
          {{ formatTime(record.created_at) }}
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="showModal(record)" v-permission="'agent:llm:update'">编辑</a-button>
            <a-popconfirm title="确定删除该 LLM 配置？" @confirm="handleDelete(record)" v-permission="'agent:llm:delete'">
              <a-button type="link" size="small" danger>删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="modalVisible"
      :title="isEdit ? '编辑 LLM 配置' : '新增 LLM 配置'"
      @ok="handleSubmit"
      :confirm-loading="submitLoading"
      width="620px"
    >
      <a-form :model="formState" :label-col="{ span: 6 }" :wrapper-col="{ span: 16 }">
        <a-form-item label="名称" required>
          <a-input v-model:value="formState.name" placeholder="如：我的 DeepSeek" />
        </a-form-item>
        <a-form-item label="供应商" required>
          <a-select
            v-model:value="formState.provider"
            placeholder="选择供应商"
            :options="providerOptions"
          />
        </a-form-item>
        <a-form-item label="模型" required>
          <a-input v-model:value="formState.model" placeholder="如：gpt-4o / deepseek-chat" />
        </a-form-item>
        <a-form-item label="Base URL">
          <a-input
            v-model:value="formState.base_url"
            placeholder="OpenAI 兼容服务地址（可选）"
          />
        </a-form-item>
        <a-form-item :label="isEdit ? 'API Key（留空不修改）' : 'API Key'">
          <a-input-password
            v-model:value="formState.api_key"
            placeholder="sk-..."
            autocomplete="new-password"
          />
        </a-form-item>
        <a-form-item label="Temperature">
          <a-input-number v-model:value="formState.temperature" :min="0" :max="2" :step="0.1" style="width: 200px" />
        </a-form-item>
        <a-form-item label="Max Tokens">
          <a-input-number v-model:value="formState.max_tokens" :min="1" :max="100000" :step="100" style="width: 200px" />
        </a-form-item>
        <a-form-item label="超时(秒)">
          <a-input-number v-model:value="formState.timeout" :min="1" :max="600" style="width: 200px" />
        </a-form-item>
        <a-form-item label="状态">
          <a-switch v-model:checked="formState.enabled" checked-children="启用" un-checked-children="停用" />
        </a-form-item>
        <a-form-item label="备注">
          <a-textarea v-model:value="formState.remark" :rows="2" placeholder="用途说明等（可选）" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import dayjs from 'dayjs'
import {
  listLlmConfigs,
  createLlmConfig,
  updateLlmConfig,
  deleteLlmConfig
} from '@/api/agent'

const loading = ref(false)
const submitLoading = ref(false)
const modalVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const searchText = ref('')
const enabledFilter = ref(null)

const enabledOptions = [
  { label: '启用', value: true },
  { label: '停用', value: false }
]

const providerOptions = [
  { label: 'OpenAI', value: 'openai' },
  { label: 'Azure OpenAI', value: 'azure' },
  { label: 'Anthropic', value: 'anthropic' },
  { label: 'Ollama', value: 'ollama' }
]

function providerLabel(v) {
  const p = providerOptions.find(x => x.value === v)
  return p ? p.label : (v || '-')
}

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '名称', dataIndex: 'name', key: 'name', width: 130, ellipsis: true },
  { title: '供应商', dataIndex: 'provider', key: 'provider', width: 110 },
  { title: '模型', dataIndex: 'model', key: 'model', width: 150, ellipsis: true },
  { title: 'API Key', dataIndex: 'api_key_mask', key: 'api_key_mask', width: 150 },
  { title: '状态', dataIndex: 'enabled', key: 'enabled', width: 80 },
  { title: '备注', dataIndex: 'remark', key: 'remark', ellipsis: true },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170 },
  { title: '操作', key: 'action', width: 130, fixed: 'right' }
]

const tableData = ref([])
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: (total) => `共 ${total} 条`,
  showSizeChanger: true
})

const defaultForm = () => ({
  name: '',
  provider: 'openai',
  model: '',
  base_url: '',
  api_key: '',
  temperature: 0.3,
  max_tokens: 2048,
  timeout: 60,
  enabled: true,
  remark: ''
})
const formState = reactive(defaultForm())

function formatTime(val) {
  return val ? dayjs(val).format('YYYY-MM-DD HH:mm:ss') : '-'
}

async function loadData() {
  loading.value = true
  try {
    const params = { page: pagination.current, page_size: pagination.pageSize }
    if (searchText.value) params.keyword = searchText.value
    if (enabledFilter.value !== null && enabledFilter.value !== undefined) params.enabled = enabledFilter.value
    const res = await listLlmConfigs(params)
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } finally {
    loading.value = false
  }
}

function handleReset() {
  searchText.value = ''
  enabledFilter.value = null
  pagination.current = 1
  loadData()
}

function handleTableChange(pag) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadData()
}

function showModal(record) {
  isEdit.value = !!record
  if (record) {
    editId.value = record.id
    Object.assign(formState, {
      name: record.name,
      provider: record.provider,
      model: record.model,
      base_url: record.base_url || '',
      api_key: '', // 不回显，留空表示不修改
      temperature: record.temperature,
      max_tokens: record.max_tokens,
      timeout: record.timeout,
      enabled: record.enabled,
      remark: record.remark || ''
    })
  } else {
    editId.value = null
    Object.assign(formState, defaultForm())
  }
  modalVisible.value = true
}

async function handleSubmit() {
  if (!formState.name.trim() || !formState.model.trim()) {
    message.warning('请填写名称和模型')
    return
  }
  submitLoading.value = true
  try {
    const payload = { ...formState }
    if (isEdit.value && !payload.api_key) delete payload.api_key
    if (isEdit.value) {
      await updateLlmConfig(editId.value, payload)
      message.success('更新成功')
    } else {
      await createLlmConfig(payload)
      message.success('创建成功')
    }
    modalVisible.value = false
    loadData()
  } finally {
    submitLoading.value = false
  }
}

async function handleDelete(record) {
  await deleteLlmConfig(record.id)
  message.success('删除成功')
  loadData()
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.page-header {
  margin-bottom: 16px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
}
</style>
