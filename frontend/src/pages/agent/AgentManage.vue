<template>
  <div>
    <div class="page-header">
      <a-space wrap>
        <a-select
          v-if="isSuperuser"
          v-model:value="scope"
          style="width: 120px"
          :options="[
            { label: '我的 Agent', value: 'mine' },
            { label: '全部 Agent', value: 'all' }
          ]"
          @change="loadData"
        />
        <a-input-search
          v-model:value="searchText"
          placeholder="搜索名称"
          style="width: 220px"
          allow-clear
          @search="handleReset"
        />
        <a-button @click="handleReset">重置</a-button>
        <a-button type="primary" @click="showModal()">
          <PlusOutlined /> 新建 Agent
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
      :scroll="{ x: 1000 }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'llm'">
          <span v-if="record.llm_name">
            {{ record.llm_name }}
            <a-tag v-if="record.llm_model" color="blue">{{ record.llm_model }}</a-tag>
          </span>
          <span v-else>-</span>
        </template>
        <template v-if="column.key === 'tools'">
          <template v-if="record.tools && record.tools.length">
            <a-tag v-for="t in record.tools" :key="t" color="green">{{ t }}</a-tag>
          </template>
          <span v-else class="no-tool">未启用工具</span>
        </template>
        <template v-if="column.key === 'enabled'">
          <a-switch
            :checked="record.enabled"
            :disabled="!canManage(record)"
            @change="(checked) => handleToggleEnabled(record, checked)"
          />
        </template>
        <template v-if="column.key === 'updated_at'">
          {{ formatTime(record.updated_at) }}
        </template>
        <template v-if="column.key === 'action' && canManage(record)">
          <a-space>
            <a-button type="link" size="small" @click="showModal(record)">编辑</a-button>
            <a-popconfirm
              title="删除 Agent 前需先删除其所有会话，确定删除？"
              @confirm="handleDelete(record.id)"
            >
              <a-button type="link" size="small" danger>删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="modalVisible"
      :title="isEdit ? '编辑 Agent' : '新建 Agent'"
      @ok="handleSubmit"
      :confirm-loading="submitLoading"
      width="640px"
    >
      <a-form :model="formState" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }">
        <a-form-item label="名称" required>
          <a-input v-model:value="formState.name" placeholder="Agent 名称" />
        </a-form-item>
        <a-form-item label="描述">
          <a-input v-model:value="formState.description" placeholder="一句话描述该 Agent 的用途（可选）" />
        </a-form-item>
        <a-form-item label="LLM 模型" required>
          <a-select
            v-model:value="formState.llm_id"
            placeholder="选择平台已配置的 LLM"
            style="width: 100%"
            :options="llmOptions"
          >
            <template #option="{ label, llm }">
              <div class="llm-option">
                <span>{{ llm.name }}</span>
                <a-tag color="blue">{{ llm.model }}</a-tag>
                <a-tag v-if="!llm.enabled" color="red">已停用</a-tag>
              </div>
            </template>
          </a-select>
        </a-form-item>
        <a-form-item label="系统提示词">
          <a-textarea
            v-model:value="formState.system_prompt"
            :rows="4"
            placeholder="直接输入提示词文字（可选），如：你是一位专业的 Python 工程师……"
          />
        </a-form-item>
        <a-form-item label="可用工具">
          <a-checkbox-group
            v-model:value="formState.tools"
            class="tool-group"
          >
            <a-checkbox v-for="t in toolList" :key="t.name" :value="t.name" class="tool-item">
              <span>{{ t.name }}</span>
            </a-checkbox>
          </a-checkbox-group>
          <div v-if="!toolList.length" class="tool-empty">暂无可用工具</div>
        </a-form-item>
        <a-form-item v-if="isEdit" label="状态">
          <a-switch v-model:checked="formState.enabled" checked-children="启用" un-checked-children="停用" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import dayjs from 'dayjs'
import { useAuthStore } from '@/stores/auth'
import {
  listAgents,
  createAgent,
  updateAgent,
  deleteAgent,
  listLlmConfigs,
  getAgentTools
} from '@/api/agent'

const authStore = useAuthStore()
const isSuperuser = computed(() => !!authStore.userInfo?.is_superuser)

const loading = ref(false)
const submitLoading = ref(false)
const modalVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const scope = ref('mine')
const searchText = ref('')

const llmOptions = ref([]) // [{ value, label, llm }]
const toolList = ref([]) // [{ name, description }]

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '名称', dataIndex: 'name', key: 'name', width: 130, ellipsis: true },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: 'LLM', key: 'llm', width: 220 },
  { title: '提示词', dataIndex: 'system_prompt', key: 'system_prompt', ellipsis: true },
  { title: '工具', key: 'tools', width: 220 },
  { title: '启用', key: 'enabled', width: 80 },
  { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 170 },
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
  description: '',
  llm_id: undefined,
  system_prompt: '',
  tools: [],
  enabled: true
})
const formState = reactive(defaultForm())

function canManage(record) {
  if (!record) return false
  if (isSuperuser.value) return true
  return authStore.userInfo?.id === record.user_id
}

function formatTime(val) {
  return val ? dayjs(val).format('YYYY-MM-DD HH:mm:ss') : '-'
}

async function loadData() {
  loading.value = true
  try {
    const params = { page: pagination.current, page_size: pagination.pageSize, scope: scope.value }
    if (searchText.value) params.keyword = searchText.value
    const res = await listAgents(params)
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } finally {
    loading.value = false
  }
}

async function loadMeta() {
  // LLM 下拉
  try {
    const llmRes = await listLlmConfigs({ page: 1, page_size: 100 })
    llmOptions.value = (llmRes.data.items || []).map(llm => ({
      value: llm.id,
      label: `${llm.name}(${llm.model})`,
      llm
    }))
  } catch (e) {
    llmOptions.value = []
  }
  // 工具列表
  try {
    const toolRes = await getAgentTools()
    toolList.value = toolRes.data?.tools || []
  } catch (e) {
    toolList.value = []
  }
}

function handleReset() {
  searchText.value = ''
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
      description: record.description || '',
      llm_id: record.llm_id,
      system_prompt: record.system_prompt || '',
      tools: record.tools || [],
      enabled: record.enabled
    })
  } else {
    editId.value = null
    Object.assign(formState, defaultForm())
  }
  modalVisible.value = true
}

async function handleSubmit() {
  if (!formState.name.trim()) {
    message.warning('请填写 Agent 名称')
    return
  }
  if (!formState.llm_id) {
    message.warning('请选择 LLM 模型')
    return
  }
  submitLoading.value = true
  try {
    if (isEdit.value) {
      await updateAgent(editId.value, { ...formState })
      message.success('更新成功')
    } else {
      await createAgent({ ...formState })
      message.success('创建成功')
    }
    modalVisible.value = false
    loadData()
  } finally {
    submitLoading.value = false
  }
}

async function handleToggleEnabled(record, checked) {
  try {
    await updateAgent(record.id, { enabled: checked })
    record.enabled = checked
    message.success(checked ? '已启用' : '已停用')
  } catch (e) {
    // 错误已由拦截器提示
  }
}

async function handleDelete(id) {
  await deleteAgent(id)
  message.success('删除成功')
  loadData()
}

onMounted(() => {
  loadData()
  loadMeta()
})
</script>

<style scoped>
.page-header {
  margin-bottom: 16px;
}
.llm-option {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.no-tool {
  color: #999;
  font-size: 12px;
}
.tool-group {
  width: 100%;
  display: flex;
  flex-direction: column;
}
.tool-item {
  margin: 0 0 6px !important;
}
.tool-empty {
  color: #999;
  font-size: 12px;
}
</style>
