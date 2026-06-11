<template>
  <div>
    <div class="page-header">
      <a-space>
        <a-button type="primary" @click="showModal()">
          <PlusOutlined /> 新增部门
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
        <template v-if="column.key === 'status'">
          <a-tag :color="record.status ? 'green' : 'red'">
            {{ record.status ? '正常' : '停用' }}
          </a-tag>
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="showModal(record)">编辑</a-button>
            <a-button type="link" size="small" @click="showModal(null, record.id)">新增子部门</a-button>
            <a-popconfirm title="确定删除该部门？" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger>删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="modalVisible"
      :title="isEdit ? '编辑部门' : '新增部门'"
      @ok="handleSubmit"
      :confirm-loading="submitLoading"
    >
      <a-form :model="formState" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }">
        <a-form-item label="上级部门">
          <a-tree-select
            v-model:value="formState.parent_id"
            placeholder="无上级部门"
            allow-clear
            :tree-data="treeData"
            :field-names="{ label: 'name', value: 'id', children: 'children' }"
            tree-default-expand-all
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item label="部门名称" required>
          <a-input v-model:value="formState.name" placeholder="请输入部门名称" />
        </a-form-item>
        <a-form-item label="部门编码">
          <a-input v-model:value="formState.code" placeholder="请输入部门编码" />
        </a-form-item>
        <a-form-item label="负责人">
          <a-input v-model:value="formState.leader" placeholder="请输入负责人" />
        </a-form-item>
        <a-form-item label="联系电话">
          <a-input v-model:value="formState.phone" placeholder="请输入联系电话" />
        </a-form-item>
        <a-form-item label="排序">
          <a-input-number v-model:value="formState.sort" :min="0" style="width: 100%" />
        </a-form-item>
        <a-form-item label="状态">
          <a-switch v-model:checked="formState.status" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { getDepartmentTree, createDepartment, updateDepartment, deleteDepartment } from '@/api/department'

const loading = ref(false)
const submitLoading = ref(false)
const modalVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const treeData = ref([])

const columns = [
  { title: '部门名称', dataIndex: 'name', key: 'name', width: 200 },
  { title: '编码', dataIndex: 'code', key: 'code', width: 120 },
  { title: '负责人', dataIndex: 'leader', key: 'leader', width: 100 },
  { title: '联系电话', dataIndex: 'phone', key: 'phone', width: 140 },
  { title: '排序', dataIndex: 'sort', key: 'sort', width: 70 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 80 },
  { title: '操作', key: 'action', width: 200, fixed: 'right' }
]

const formState = reactive({
  name: '',
  code: '',
  parent_id: null,
  sort: 0,
  leader: '',
  phone: '',
  status: true
})

async function loadData() {
  loading.value = true
  try {
    const res = await getDepartmentTree()
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
      code: record.code || '',
      parent_id: record.parent_id,
      sort: record.sort,
      leader: record.leader || '',
      phone: record.phone || '',
      status: record.status
    })
  } else {
    editId.value = null
    Object.assign(formState, {
      name: '',
      code: '',
      parent_id: parentId || null,
      sort: 0,
      leader: '',
      phone: '',
      status: true
    })
  }
  modalVisible.value = true
}

async function handleSubmit() {
  submitLoading.value = true
  try {
    if (isEdit.value) {
      await updateDepartment(editId.value, formState)
      message.success('更新成功')
    } else {
      await createDepartment(formState)
      message.success('创建成功')
    }
    modalVisible.value = false
    loadData()
  } finally {
    submitLoading.value = false
  }
}

async function handleDelete(id) {
  await deleteDepartment(id)
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
