<template>
  <div>
    <div class="page-header">
      <a-space>
        <a-input-search
          v-model:value="searchText"
          placeholder="搜索用户名"
          style="width: 240px"
          @search="loadData"
          allow-clear
        />
        <a-button type="primary" @click="showModal()" v-permission="'user:create'">
          <PlusOutlined /> 新增用户
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
        <template v-if="column.key === 'is_active'">
          <a-tag :color="record.is_active ? 'green' : 'red'">
            {{ record.is_active ? '启用' : '禁用' }}
          </a-tag>
        </template>
        <template v-if="column.key === 'department_id'">
          {{ getDeptName(record.department_id) }}
        </template>
        <template v-if="column.key === 'roles'">
          <a-tag v-for="role in (record.roles || [])" :key="role.id" color="blue">{{ role.name }}</a-tag>
          <span v-if="!record.roles?.length">-</span>
        </template>
        <template v-if="column.key === 'created_at'">
          {{ formatDate(record.created_at) }}
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="showModal(record)" v-permission="'user:update'">编辑</a-button>
            <a-popconfirm title="确定删除该用户？" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger v-permission="'user:delete'">删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="modalVisible"
      :title="isEdit ? '编辑用户' : '新增用户'"
      @ok="handleSubmit"
      :confirm-loading="submitLoading"
      width="560px"
    >
      <a-form :model="formState" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }">
        <a-form-item label="用户名" v-if="!isEdit" required>
          <a-input v-model:value="formState.username" placeholder="请输入用户名" />
        </a-form-item>
        <a-form-item label="邮箱" required>
          <a-input v-model:value="formState.email" placeholder="请输入邮箱" />
        </a-form-item>
        <a-form-item label="密码" v-if="!isEdit" required>
          <a-input-password v-model:value="formState.password" placeholder="请输入密码" />
        </a-form-item>
        <a-form-item label="昵称">
          <a-input v-model:value="formState.nickname" placeholder="请输入昵称" />
        </a-form-item>
        <a-form-item label="手机号">
          <a-input v-model:value="formState.phone" placeholder="请输入手机号" />
        </a-form-item>
        <a-form-item label="部门">
          <a-tree-select
            v-model:value="formState.department_id"
            placeholder="请选择部门"
            allow-clear
            :tree-data="deptTreeData"
            :field-names="{ label: 'name', value: 'id', children: 'children' }"
            tree-default-expand-all
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item label="角色">
          <a-select
            v-model:value="formState.role_ids"
            mode="multiple"
            placeholder="请选择角色"
            :options="roleOptions"
            :loading="rolesLoading"
          />
        </a-form-item>
        <a-form-item label="状态" v-if="isEdit">
          <a-switch v-model:checked="formState.is_active" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { getUsers, getUser, createUser, updateUser, deleteUser } from '@/api/user'
import { getRoles } from '@/api/role'
import { getDepartmentTree } from '@/api/department'
import dayjs from 'dayjs'

const loading = ref(false)
const submitLoading = ref(false)
const modalVisible = ref(false)
const isEdit = ref(false)
const searchText = ref('')
const editId = ref(null)
const rolesLoading = ref(false)
const roleOptions = ref([])
const deptTreeData = ref([])
const deptFlatMap = ref({})

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '用户名', dataIndex: 'username', key: 'username' },
  { title: '邮箱', dataIndex: 'email', key: 'email' },
  { title: '昵称', dataIndex: 'nickname', key: 'nickname' },
  { title: '部门', dataIndex: 'department_id', key: 'department_id', width: 120 },
  { title: '角色', key: 'roles', width: 160 },
  { title: '状态', dataIndex: 'is_active', key: 'is_active', width: 80 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: '操作', key: 'action', width: 140, fixed: 'right' }
]

const tableData = ref([])
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: (total) => `共 ${total} 条`,
  showSizeChanger: true
})

const formState = reactive({
  username: '',
  email: '',
  password: '',
  nickname: '',
  phone: '',
  department_id: null,
  role_ids: [],
  is_active: true
})

function formatDate(val) {
  return val ? dayjs(val).format('YYYY-MM-DD HH:mm:ss') : '-'
}

// 构建部门扁平映射，用于根据 id 查名称
function buildDeptFlatMap(nodes) {
  for (const node of nodes) {
    deptFlatMap.value[node.id] = node.name
    if (node.children?.length) {
      buildDeptFlatMap(node.children)
    }
  }
}

function getDeptName(deptId) {
  if (!deptId) return '-'
  return deptFlatMap.value[deptId] || deptId
}

async function loadData() {
  loading.value = true
  try {
    const res = await getUsers({
      page: pagination.current,
      page_size: pagination.pageSize
    })
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } finally {
    loading.value = false
  }
}

async function loadRoles() {
  rolesLoading.value = true
  try {
    const res = await getRoles({ page: 1, page_size: 100 })
    roleOptions.value = (res.data.items || []).map(r => ({
      label: r.name,
      value: r.id
    }))
  } finally {
    rolesLoading.value = false
  }
}

async function loadDeptTree() {
  try {
    const res = await getDepartmentTree()
    deptTreeData.value = res.data || []
    deptFlatMap.value = {}
    buildDeptFlatMap(deptTreeData.value)
  } catch (e) {
    deptTreeData.value = []
  }
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
      username: record.username,
      email: record.email,
      password: '',
      nickname: record.nickname || '',
      phone: record.phone || '',
      department_id: record.department_id,
      role_ids: [],
      is_active: record.is_active
    })
    // 异步加载用户详情（含角色）
    loadUserDetail(record.id)
  } else {
    editId.value = null
    Object.assign(formState, {
      username: '',
      email: '',
      password: '',
      nickname: '',
      phone: '',
      department_id: null,
      role_ids: [],
      is_active: true
    })
  }
  modalVisible.value = true
}

async function loadUserDetail(userId) {
  try {
    const res = await getUser(userId)
    const detail = res.data
    formState.role_ids = detail.roles?.map(r => r.id) || []
  } catch (e) {
    // 静默处理
  }
}

async function handleSubmit() {
  submitLoading.value = true
  try {
    if (isEdit.value) {
      const data = { ...formState }
      delete data.username
      delete data.password
      await updateUser(editId.value, data)
      message.success('更新成功')
    } else {
      await createUser(formState)
      message.success('创建成功')
    }
    modalVisible.value = false
    loadData()
  } finally {
    submitLoading.value = false
  }
}

async function handleDelete(id) {
  await deleteUser(id)
  message.success('删除成功')
  loadData()
}

onMounted(() => {
  loadData()
  loadRoles()
  loadDeptTree()
})
</script>

<style scoped>
.page-header {
  margin-bottom: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
