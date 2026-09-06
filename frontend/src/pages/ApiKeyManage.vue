<template>
  <div>
    <div class="page-header">
      <a-space>
        <a-button type="primary" @click="showCreateModal" v-permission="'api-key:create'">
          <PlusOutlined /> 新增密钥
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
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'key_prefix'">
          <a-typography-text code>{{ record.key_prefix }}...</a-typography-text>
        </template>
        <template v-if="column.key === 'role_id'">
          <a-tag v-if="record.role_id" color="blue">{{ getRoleName(record.role_id) }}</a-tag>
          <span v-else>未关联</span>
        </template>
        <template v-if="column.key === 'expires_at'">
          <span v-if="record.expires_at">{{ formatDate(record.expires_at) }}</span>
          <a-tag v-else color="green">永不过期</a-tag>
        </template>
        <template v-if="column.key === 'is_active'">
          <a-switch
            :checked="record.is_active"
            checked-children="启"
            un-checked-children="停"
            @change="(checked) => handleToggleStatus(record, checked)"
            v-permission="'api-key:update'"
          />
        </template>
        <template v-if="column.key === 'last_used_at'">
          {{ record.last_used_at ? formatDate(record.last_used_at) : '从未使用' }}
        </template>
        <template v-if="column.key === 'created_at'">
          {{ formatDate(record.created_at) }}
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="handleRegenerate(record.id)" v-permission="'api-key:update'">重新生成</a-button>
            <a-popconfirm title="确定删除该密钥？" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger v-permission="'api-key:delete'">删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 新增密钥弹窗 -->
    <a-modal
      v-model:open="modalVisible"
      title="新增密钥"
      @ok="handleSubmit"
      :confirm-loading="submitLoading"
      width="560px"
    >
      <a-form :model="formState" :rules="formRules" ref="formRef" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }">
        <a-form-item name="name" label="密钥名称" required>
          <a-input v-model:value="formState.name" placeholder="请输入密钥名称" />
        </a-form-item>
        <a-form-item name="role_id" label="关联角色" required>
          <a-select v-model:value="formState.role_id" placeholder="请选择关联角色" :options="roleOptions" />
        </a-form-item>
        <a-form-item label="过期时间">
          <a-date-picker
            v-model:value="formState.expires_at"
            show-time
            value-format="YYYY-MM-DD HH:mm:ss"
            placeholder="留空则永不过期"
            style="width: 100%"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 创建成功弹窗：展示完整密钥 -->
    <a-modal
      v-model:open="keyResultVisible"
      title="密钥创建成功"
      :footer="null"
      @cancel="keyResultVisible = false"
    >
      <a-alert
        type="warning"
        show-icon
        message="请立即复制并安全保存此密钥，关闭后将无法再次查看完整密钥！"
        style="margin-bottom: 16px"
      />
      <a-typography-text code style="font-size: 14px; word-break: break-all; display: block; margin-bottom: 16px;">
        {{ createdFullKey }}
      </a-typography-text>
      <a-space>
        <a-button type="primary" @click="copyKey">复制密钥</a-button>
        <a-button @click="keyResultVisible = false">关闭</a-button>
      </a-space>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { getApiKeys, getApiKeyRoles, createApiKey, updateApiKeyStatus, deleteApiKey, regenerateApiKey } from '@/api/api_key'
import dayjs from 'dayjs'

const loading = ref(false)
const submitLoading = ref(false)
const modalVisible = ref(false)
const keyResultVisible = ref(false)
const createdFullKey = ref('')
const roleOptions = ref([])
const roleMap = ref({})

const tableData = ref([])
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  pageSizeOptions: ['10', '20', '50', '100'],
})

const formRef = ref(null)
const formState = reactive({
  name: '',
  role_id: undefined,
  expires_at: undefined,
})

const formRules = {
  name: [{ required: true, message: '请输入密钥名称', trigger: 'blur' }],
  role_id: [{ required: true, message: '请选择关联角色', trigger: 'change' }],
}

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '名称', dataIndex: 'name', key: 'name', ellipsis: true },
  { title: '密钥前缀', key: 'key_prefix', width: 180 },
  { title: '关联角色', key: 'role_id', width: 120 },
  { title: '过期时间', key: 'expires_at', width: 170 },
  { title: '状态', key: 'is_active', width: 80 },
  { title: '最后使用', key: 'last_used_at', width: 160 },
  { title: '创建时间', key: 'created_at', width: 160 },
  { title: '操作', key: 'action', width: 240 },
]

function formatDate(val) {
  return val ? dayjs(val).format('YYYY-MM-DD HH:mm') : ''
}

function getRoleName(roleId) {
  return roleMap.value[roleId] || `角色(${roleId})`
}

async function loadRoles() {
  try {
    const res = await getApiKeyRoles()
    if (res.code === 200 && res.data) {
      roleOptions.value = res.data.map(r => ({ label: r.name, value: r.id }))
      roleMap.value = {}
      res.data.forEach(r => { roleMap.value[r.id] = r.name })
    }
  } catch (e) {
    // 静默
  }
}

async function loadData() {
  loading.value = true
  try {
    const res = await getApiKeys({
      page: pagination.current,
      page_size: pagination.pageSize,
    })
    if (res.code === 200 && res.data) {
      tableData.value = res.data.items || []
      pagination.total = res.data.total || 0
    }
  } catch (e) {
    message.error('加载密钥列表失败')
  } finally {
    loading.value = false
  }
}

function handleTableChange(pag) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadData()
}

function resetForm() {
  formState.name = ''
  formState.role_id = undefined
  formState.expires_at = undefined
  formRef.value?.clearValidate()
}

function showCreateModal() {
  resetForm()
  modalVisible.value = true
}

async function handleSubmit() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  submitLoading.value = true
  try {
    const res = await createApiKey({
      name: formState.name,
      role_id: formState.role_id || null,
      expires_at: formState.expires_at || null,
    })
    if (res.code === 200 && res.data) {
      modalVisible.value = false
      createdFullKey.value = res.data.full_key
      keyResultVisible.value = true
      loadData()
    }
  } catch (e) {
    // 错误已由拦截器处理
  } finally {
    submitLoading.value = false
  }
}

async function handleToggleStatus(record, checked) {
  try {
    const res = await updateApiKeyStatus(record.id, checked)
    if (res.code === 200) {
      record.is_active = checked
      message.success(res.message || (checked ? '已启用' : '已禁用'))
    } else {
      loadData()
    }
  } catch (e) {
    // 错误已由拦截器处理
    loadData()
  }
}

async function handleDelete(id) {
  try {
    const res = await deleteApiKey(id)
    if (res.code === 200) {
      message.success('删除成功')
      loadData()
    }
  } catch (e) {
    // 错误已由拦截器处理
  }
}

async function handleRegenerate(id) {
  try {
    const res = await regenerateApiKey(id)
    if (res.code === 200 && res.data) {
      createdFullKey.value = res.data.full_key
      keyResultVisible.value = true
      loadData()
    }
  } catch (e) {
    // 错误已由拦截器处理
  }
}

function copyKey() {
  if (createdFullKey.value) {
    navigator.clipboard.writeText(createdFullKey.value).then(() => {
      message.success('已复制到剪贴板')
    }).catch(() => {
      // 降级方案
      const ta = document.createElement('textarea')
      ta.value = createdFullKey.value
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      message.success('已复制到剪贴板')
    })
  }
}

onMounted(() => {
  loadRoles()
  loadData()
})
</script>

<style scoped>
.page-header {
  margin-bottom: 16px;
}
</style>