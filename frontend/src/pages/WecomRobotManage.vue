<template>
  <div>
    <div class="page-header">
      <a-space>
        <a-input-search
          v-model:value="searchText"
          placeholder="搜索机器人名称"
          style="width: 220px"
          @search="handleSearch"
          allow-clear
        />
        <a-select
          v-model:value="enabledFilter"
          placeholder="状态"
          style="width: 110px"
          allow-clear
          :options="[
            { label: '已启用', value: true },
            { label: '已停用', value: false }
          ]"
          @change="loadData"
        />
        <a-button @click="handleReset">重置</a-button>
        <a-button type="primary" @click="showCreateModal" v-permission="'wecom-robot:create'">
          <PlusOutlined /> 新增机器人
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
      size="middle"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'webhook'">
          <a-typography-text code>{{ record.masked_webhook }}</a-typography-text>
        </template>
        <template v-if="column.key === 'secret'">
          <a-tag v-if="record.has_secret" color="green">已加签</a-tag>
          <a-tag v-else>未加签</a-tag>
        </template>
        <template v-if="column.key === 'enabled'">
          <a-switch
            :checked="record.enabled"
            checked-children="启"
            un-checked-children="停"
            @change="(checked) => handleToggleEnabled(record, checked)"
            v-permission="'wecom-robot:update'"
          />
        </template>
        <template v-if="column.key === 'created_at'">
          {{ formatDate(record.created_at) }}
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="handleTest(record)" v-permission="'wecom-robot:update'">测试消息</a-button>
            <a-button type="link" size="small" @click="showEditModal(record)" v-permission="'wecom-robot:update'">编辑</a-button>
            <a-popconfirm title="确定删除该机器人？" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger v-permission="'wecom-robot:delete'">删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 新增/编辑弹窗 -->
    <a-modal
      v-model:open="modalVisible"
      :title="isEdit ? '编辑机器人' : '新增机器人'"
      @ok="handleSubmit"
      :confirm-loading="submitLoading"
      width="620px"
    >
      <a-form :model="formState" :rules="formRules" ref="formRef" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }">
        <a-form-item name="name" label="机器人名称" required>
          <a-input v-model:value="formState.name" placeholder="如：测试部-质量群" />
        </a-form-item>
        <a-form-item name="webhook_url" :label="isEdit ? 'Webhook（新）' : 'Webhook'" :required="!isEdit">
          <a-input
            v-model:value="formState.webhook_url"
            :placeholder="isEdit ? '留空表示不修改' : 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx'"
          />
          <div v-if="isEdit" class="form-hint">
            当前配置（脱敏）：<a-typography-text code>{{ maskedWebhook }}</a-typography-text>；如需更换请完整粘贴新的 webhook
          </div>
        </a-form-item>
        <a-form-item name="secret" label="加签密钥">
          <a-input-password v-model:value="formState.secret" :placeholder="isEdit ? '留空表示不修改（已加密保存）' : '选填，群机器人「安全设置-加签」的密钥'" />
        </a-form-item>
        <a-form-item v-if="isEdit" name="enabled" label="启用状态">
          <a-switch v-model:checked="formState.enabled" checked-children="启" un-checked-children="停" />
        </a-form-item>
        <a-form-item name="description" label="备注">
          <a-textarea v-model:value="formState.description" :rows="3" placeholder="用途/所属群说明（选填）" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import {
  getWecomRobots,
  createWecomRobot,
  updateWecomRobot,
  deleteWecomRobot,
  testWecomRobot
} from '@/api/wecomRobot'
import dayjs from 'dayjs'

const loading = ref(false)
const submitLoading = ref(false)
const modalVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const searchText = ref('')
const enabledFilter = ref(null)
const maskedWebhook = ref('')

const tableData = ref([])
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  pageSizeOptions: ['10', '20', '50', '100']
})

const formRef = ref(null)
const formState = reactive({
  name: '',
  webhook_url: '',
  secret: '',
  enabled: true,
  description: ''
})

const formRules = {
  name: [{ required: true, message: '请输入机器人名称', trigger: 'blur' }]
}

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '名称', dataIndex: 'name', key: 'name', width: 180, ellipsis: true },
  { title: 'Webhook', key: 'webhook', ellipsis: true },
  { title: '加签', key: 'secret', width: 90 },
  { title: '状态', key: 'enabled', width: 80 },
  { title: '备注', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '创建时间', key: 'created_at', width: 160 },
  { title: '操作', key: 'action', width: 200, fixed: 'right' }
]

function formatDate(val) {
  return val ? dayjs(val).format('YYYY-MM-DD HH:mm') : '-'
}

async function loadData() {
  loading.value = true
  try {
    const params = { page: pagination.current, page_size: pagination.pageSize }
    if (searchText.value) params.keyword = searchText.value
    if (enabledFilter.value !== null && enabledFilter.value !== undefined) params.enabled = enabledFilter.value
    const res = await getWecomRobots(params)
    if (res.code === 200 && res.data) {
      tableData.value = res.data.items || []
      pagination.total = res.data.total || 0
    }
  } catch (e) {
    // 错误已由拦截器处理
  } finally {
    loading.value = false
  }
}

function handleTableChange(pag) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadData()
}

function handleSearch() {
  pagination.current = 1
  loadData()
}

function handleReset() {
  searchText.value = ''
  enabledFilter.value = null
  pagination.current = 1
  loadData()
}

function resetForm() {
  formState.name = ''
  formState.webhook_url = ''
  formState.secret = ''
  formState.enabled = true
  formState.description = ''
  maskedWebhook.value = ''
  formRef.value?.clearValidate()
}

function showCreateModal() {
  isEdit.value = false
  editId.value = null
  resetForm()
  modalVisible.value = true
}

function showEditModal(record) {
  isEdit.value = true
  editId.value = record.id
  resetForm()
  formState.name = record.name
  formState.enabled = !!record.enabled
  formState.description = record.description || ''
  maskedWebhook.value = record.masked_webhook || ''
  modalVisible.value = true
}

function buildPayload() {
  const payload = { name: formState.name, description: formState.description || null }
  if (!isEdit.value) {
    payload.webhook_url = formState.webhook_url.trim()
    if (formState.secret) payload.secret = formState.secret
  } else {
    payload.enabled = formState.enabled
    // webhook/secret 留空 = 不修改
    if (formState.webhook_url && formState.webhook_url.trim()) payload.webhook_url = formState.webhook_url.trim()
    if (formState.secret) payload.secret = formState.secret
  }
  return payload
}

async function doSubmit() {
  submitLoading.value = true
  try {
    const payload = buildPayload()
    let res
    if (isEdit.value) {
      res = await updateWecomRobot(editId.value, payload)
      message.success('保存成功')
    } else {
      res = await createWecomRobot(payload)
      message.success('新增成功')
    }
    if (res && res.code === 200) {
      modalVisible.value = false
      loadData()
    }
  } catch (e) {
    // 错误已由拦截器处理
  } finally {
    submitLoading.value = false
  }
}

async function handleSubmit() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  if (!isEdit.value && !formState.webhook_url.trim()) {
    message.warning('请输入 webhook 地址')
    return
  }
  if (isEdit.value && formState.webhook_url && formState.webhook_url.trim()) {
    Modal.confirm({
      title: '确认更换 Webhook？',
      content: '更换后将向新的 webhook 推送测试结果，请确认地址无误。',
      okText: '确认更换',
      cancelText: '取消',
      onOk: doSubmit
    })
  } else {
    doSubmit()
  }
}

async function handleToggleEnabled(record, checked) {
  try {
    const res = await updateWecomRobot(record.id, { enabled: checked })
    if (res.code === 200) {
      record.enabled = checked
      message.success(checked ? '已启用' : '已停用')
    } else {
      loadData()
    }
  } catch (e) {
    loadData()
  }
}

async function handleTest(record) {
  try {
    const res = await testWecomRobot(record.id)
    if (res.code === 200) {
      message.success('测试消息发送成功，请到群里查看')
    }
  } catch (e) {
    // 错误已由拦截器处理（含企业微信返回的具体错误）
  }
}

async function handleDelete(id) {
  try {
    const res = await deleteWecomRobot(id)
    if (res.code === 200) {
      message.success('删除成功')
      loadData()
    }
  } catch (e) {
    // 被计划引用时后端拒绝，拦截器已提示
  }
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
  align-items: center;
}
.form-hint {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}
</style>
