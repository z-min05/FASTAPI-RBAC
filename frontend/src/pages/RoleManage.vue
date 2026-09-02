<template>
  <div>
    <div class="page-header">
      <a-space>
        <a-input-search
          v-model:value="searchText"
          placeholder="搜索角色名称"
          style="width: 240px"
          @search="loadData"
          allow-clear
        />
        <a-button type="primary" @click="showModal()" v-permission="'role:create'">
          <PlusOutlined /> 新增角色
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
        <template v-if="column.key === 'created_at'">
          {{ formatDate(record.created_at) }}
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="showModal(record)" v-permission="'role:update'">编辑</a-button>
            <a-popconfirm title="确定删除该角色？" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger v-permission="'role:delete'">删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="modalVisible"
      :title="isEdit ? '编辑角色' : '新增角色'"
      @ok="handleSubmit"
      :confirm-loading="submitLoading"
      width="600px"
    >
      <a-form :model="formState" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }">
        <a-form-item label="角色名称" required>
          <a-input v-model:value="formState.name" placeholder="请输入角色名称" />
        </a-form-item>
        <a-form-item label="角色编码" required>
          <a-input v-model:value="formState.code" placeholder="请输入角色编码" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="formState.description" placeholder="请输入描述" :rows="3" />
        </a-form-item>
        <a-form-item label="排序">
          <a-input-number v-model:value="formState.sort" :min="0" style="width: 100%" />
        </a-form-item>
        <a-form-item label="权限">
          <a-select
            v-model:value="formState.permission_ids"
            mode="multiple"
            placeholder="请选择权限"
            :options="permOptions"
            :loading="permsLoading"
          />
        </a-form-item>
        <a-form-item label="菜单权限">
          <a-tree
            v-model:checkedKeys="menuCheckedKeys"
            :tree-data="menuTreeData"
            checkable
            check-strictly
            :field-names="{ title: 'name', key: 'id', children: 'children' }"
            style="max-height: 360px; overflow-y: auto; border: 1px solid #d9d9d9; border-radius: 6px; padding: 8px;"
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
import { getRoles, getRole, createRole, updateRole, deleteRole } from '@/api/role'
import { getPermissions } from '@/api/permission'
import { getMenuTree } from '@/api/menu'
import dayjs from 'dayjs'

const loading = ref(false)
const submitLoading = ref(false)
const modalVisible = ref(false)
const isEdit = ref(false)
const searchText = ref('')
const editId = ref(null)
const permsLoading = ref(false)
const permOptions = ref([])
const menuTreeData = ref([])

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '角色名称', dataIndex: 'name', key: 'name' },
  { title: '角色编码', dataIndex: 'code', key: 'code' },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '排序', dataIndex: 'sort', key: 'sort', width: 80 },
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
  name: '',
  code: '',
  description: '',
  sort: 0,
  is_active: true,
  permission_ids: [],
  menu_ids: []
})

// a-tree check-strictly 下 checkedKeys 是数组
const menuCheckedKeys = ref([])

function formatDate(val) {
  return val ? dayjs(val).format('YYYY-MM-DD HH:mm:ss') : '-'
}

async function loadData() {
  loading.value = true
  try {
    const res = await getRoles({
      page: pagination.current,
      page_size: pagination.pageSize
    })
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } finally {
    loading.value = false
  }
}

async function loadPerms() {
  permsLoading.value = true
  try {
    const res = await getPermissions({ page: 1, page_size: 100 })
    permOptions.value = (res.data.items || []).map(p => ({
      label: `${p.name} (${p.code})`,
      value: p.id
    }))
  } finally {
    permsLoading.value = false
  }
}

async function loadMenuTree() {
  try {
    const res = await getMenuTree()
    menuTreeData.value = res.data || []
  } catch (e) {
    menuTreeData.value = []
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
      name: record.name,
      code: record.code,
      description: record.description || '',
      sort: record.sort,
      is_active: record.is_active,
      permission_ids: [],
      menu_ids: []
    })
    menuCheckedKeys.value = []
    loadRoleDetail(record.id)
  } else {
    editId.value = null
    Object.assign(formState, {
      name: '',
      code: '',
      description: '',
      sort: 0,
      is_active: true,
      permission_ids: [],
      menu_ids: []
    })
    menuCheckedKeys.value = []
  }
  modalVisible.value = true
}

async function loadRoleDetail(roleId) {
  try {
    const res = await getRole(roleId)
    const detail = res.data
    formState.permission_ids = detail.permissions?.map(p => p.id) || []
    const menuIds = detail.menus?.map(m => m.id) || []
    menuCheckedKeys.value = menuIds
  } catch (e) {
    // 静默处理
  }
}

async function handleSubmit() {
  submitLoading.value = true
  try {
    // menuCheckedKeys 可能是 { checked: [], halfChecked: [] } 或数组
    const checkedIds = Array.isArray(menuCheckedKeys.value)
      ? menuCheckedKeys.value
      : menuCheckedKeys.value.checked || []
    const payload = {
      ...formState,
      menu_ids: checkedIds
    }
    if (isEdit.value) {
      await updateRole(editId.value, payload)
      message.success('更新成功')
    } else {
      await createRole(payload)
      message.success('创建成功')
    }
    modalVisible.value = false
    loadData()
  } finally {
    submitLoading.value = false
  }
}

async function handleDelete(id) {
  await deleteRole(id)
  message.success('删除成功')
  loadData()
}

onMounted(() => {
  loadData()
  loadPerms()
  loadMenuTree()
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
