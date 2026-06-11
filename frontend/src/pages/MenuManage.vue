<template>
  <div>
    <div class="page-header">
      <a-space>
        <a-button type="primary" @click="showModal()">
          <PlusOutlined /> 新增菜单
        </a-button>
      </a-space>
    </div>

    <a-table
      :columns="columns"
      :data-source="treeData"
      :loading="loading"
      :pagination="false"
      row-key="id"
      default-expand-all-rows
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'menu_type'">
          <a-tag v-if="record.menu_type === 'directory'" color="blue">目录</a-tag>
          <a-tag v-else-if="record.menu_type === 'menu'" color="green">菜单</a-tag>
          <a-tag v-else-if="record.menu_type === 'button'" color="orange">按钮</a-tag>
        </template>
        <template v-if="column.key === 'visible'">
          <a-tag :color="record.visible ? 'green' : 'red'">
            {{ record.visible ? '显示' : '隐藏' }}
          </a-tag>
        </template>
        <template v-if="column.key === 'icon'">
          <span v-if="record.icon">{{ record.icon }}</span>
          <span v-else>-</span>
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="showModal(record)">编辑</a-button>
            <a-button type="link" size="small" @click="showModal(null, record.id)">新增子菜单</a-button>
            <a-popconfirm title="确定删除该菜单？" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger>删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="modalVisible"
      :title="isEdit ? '编辑菜单' : '新增菜单'"
      @ok="handleSubmit"
      :confirm-loading="submitLoading"
      width="600px"
    >
      <a-form :model="formState" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }">
        <a-form-item label="上级菜单">
          <a-tree-select
            v-model:value="formState.parent_id"
            placeholder="无上级菜单"
            allow-clear
            :tree-data="treeData"
            :field-names="{ label: 'name', value: 'id', children: 'children' }"
            tree-default-expand-all
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item label="菜单类型" required>
          <a-radio-group v-model:value="formState.menu_type">
            <a-radio value="directory">目录</a-radio>
            <a-radio value="menu">菜单</a-radio>
            <a-radio value="button">按钮</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item label="菜单名称" required>
          <a-input v-model:value="formState.name" placeholder="请输入菜单名称" />
        </a-form-item>
        <a-form-item label="路由路径">
          <a-input v-model:value="formState.path" placeholder="如: /system/users" />
        </a-form-item>
        <a-form-item label="组件路径">
          <a-input v-model:value="formState.component" placeholder="如: system/UserManage" />
        </a-form-item>
        <a-form-item label="图标">
          <a-input v-model:value="formState.icon" placeholder="如: UserOutlined" />
        </a-form-item>
        <a-form-item label="权限标识">
          <a-input v-model:value="formState.permission" placeholder="如: user:list" />
        </a-form-item>
        <a-form-item label="排序">
          <a-input-number v-model:value="formState.sort" :min="0" style="width: 100%" />
        </a-form-item>
        <a-form-item label="是否显示">
          <a-switch v-model:checked="formState.visible" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { getMenuTree, createMenu, updateMenu, deleteMenu } from '@/api/menu'

const loading = ref(false)
const submitLoading = ref(false)
const modalVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const treeData = ref([])

const columns = [
  { title: '菜单名称', dataIndex: 'name', key: 'name', width: 180 },
  { title: '类型', dataIndex: 'menu_type', key: 'menu_type', width: 80 },
  { title: '图标', dataIndex: 'icon', key: 'icon', width: 120 },
  { title: '路由路径', dataIndex: 'path', key: 'path' },
  { title: '组件路径', dataIndex: 'component', key: 'component' },
  { title: '权限标识', dataIndex: 'permission', key: 'permission' },
  { title: '排序', dataIndex: 'sort', key: 'sort', width: 70 },
  { title: '可见', dataIndex: 'visible', key: 'visible', width: 70 },
  { title: '操作', key: 'action', width: 200, fixed: 'right' }
]

const formState = reactive({
  name: '',
  path: '',
  component: '',
  icon: '',
  menu_type: 'menu',
  parent_id: null,
  sort: 0,
  visible: true,
  permission: ''
})

async function loadData() {
  loading.value = true
  try {
    const res = await getMenuTree()
    treeData.value = res.data || []
  } finally {
    loading.value = false
  }
}

function showModal(record, parentId) {
  isEdit.value = !!record
  if (record) {
    editId.value = record.id
    Object.assign(formState, {
      name: record.name,
      path: record.path || '',
      component: record.component || '',
      icon: record.icon || '',
      menu_type: record.menu_type,
      parent_id: record.parent_id,
      sort: record.sort,
      visible: record.visible,
      permission: record.permission || ''
    })
  } else {
    editId.value = null
    Object.assign(formState, {
      name: '',
      path: '',
      component: '',
      icon: '',
      menu_type: 'menu',
      parent_id: parentId || null,
      sort: 0,
      visible: true,
      permission: ''
    })
  }
  modalVisible.value = true
}

async function handleSubmit() {
  submitLoading.value = true
  try {
    if (isEdit.value) {
      await updateMenu(editId.value, formState)
      message.success('更新成功')
    } else {
      await createMenu(formState)
      message.success('创建成功')
    }
    modalVisible.value = false
    loadData()
  } finally {
    submitLoading.value = false
  }
}

async function handleDelete(id) {
  await deleteMenu(id)
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
}
</style>
