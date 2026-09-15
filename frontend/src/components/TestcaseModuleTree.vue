<template>
  <div class="module-tree">
    <div class="tree-header">
      <a-input-search
        v-model:value="searchValue"
        placeholder="搜索模块"
        size="small"
        allow-clear
      />
      <a-button
        class="create-root-btn"
        type="primary"
        size="small"
        block
        v-permission="'testcase:module:create'"
        @click="openCreate(null)"
      >
        <PlusOutlined /> 新建顶级模块
      </a-button>
    </div>

    <a-spin :spinning="loading">
      <a-tree
        v-if="filteredTree.length"
        :tree-data="filteredTree"
        :field-names="{ title: 'name', key: 'id', children: 'children' }"
        block-node
        show-line
        default-expand-all
        :expanded-keys="expandedKeys"
        :selected-keys="selectedKeys"
        @expand="onExpand"
        @select="onSelect"
      >
        <template #title="node">
          <span class="node-title">
            <a-tooltip :title="node.name" placement="right" :mouse-enter-delay="0.4">
              <span class="node-name">
                <template v-for="(part, index) in highlightParts(node.name)" :key="index">
                  <span :class="{ 'keyword-hit': part.hit }">{{ part.text }}</span>
                </template>
              </span>
            </a-tooltip>
            <span class="node-tail">
              <a-badge
                v-if="node.total_case_count"
                :count="node.total_case_count"
                :number-style="{ backgroundColor: '#1677ff' }"
              />
              <span class="node-actions">
                <a-space :size="2">
                  <file-add-outlined
                    v-if="node.is_leaf"
                    class="node-icon"
                    title="在此模块新增用例"
                    @click.stop="onCreateCase(node)"
                  />
                  <plus-outlined
                    v-permission="'testcase:module:create'"
                    class="node-icon"
                    title="新增子模块"
                    @click.stop="openCreate(node)"
                  />
                  <edit-outlined
                    v-permission="'testcase:module:update'"
                    class="node-icon"
                    title="编辑模块"
                    @click.stop="openEdit(node)"
                  />
                  <a-popconfirm
                    title="确定删除该模块？"
                    placement="right"
                    @confirm="handleDelete(node)"
                  >
                    <delete-outlined
                      v-permission="'testcase:module:delete'"
                      class="node-icon node-icon-danger"
                      title="删除模块"
                      @click.stop
                    />
                  </a-popconfirm>
                </a-space>
              </span>
            </span>
          </span>
        </template>
      </a-tree>
      <a-empty v-else class="tree-empty" description="暂无模块，请先新建模块" />
    </a-spin>

    <!-- 模块新增 / 编辑 -->
    <a-modal
      v-model:open="modalVisible"
      :title="isEdit ? '编辑模块' : '新增模块'"
      ok-text="保存"
      cancel-text="取消"
      width="560px"
      :confirm-loading="submitLoading"
      @ok="handleSubmit"
    >
      <a-form :model="formState" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }">
        <a-form-item label="所属项目">
          <span class="readonly-text">{{ projectId }}</span>
        </a-form-item>
        <a-form-item label="上级模块">
          <a-tree-select
            v-model:value="formState.parent_id"
            placeholder="顶级模块"
            :tree-data="parentOptions"
            tree-default-expand-all
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item label="模块名称" required>
          <a-input v-model:value="formState.name" :maxlength="50" placeholder="请输入模块名称" />
        </a-form-item>
        <a-form-item label="目录名/文件名" required>
          <a-input v-model:value="formState.code" :maxlength="100" placeholder="如 device 或 test_comm_log" />
          <div class="code-preview">路径预览：{{ codePreview }}</div>
          <div v-if="showTestPrefixHint" class="code-hint">
            该模块暂无子模块；若要在此创建用例，文件名需以 test_ 开头
          </div>
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="formState.description" :rows="2" :maxlength="500" placeholder="选填" />
        </a-form-item>
        <a-form-item label="排序">
          <a-input-number v-model:value="formState.sort" :min="0" style="width: 100%" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { PlusOutlined, EditOutlined, DeleteOutlined, FileAddOutlined } from '@ant-design/icons-vue'
import { getModuleTree, createModule, updateModule, deleteModule } from '@/api/testcaseModule'

const props = defineProps({
  projectId: { type: Number, required: true },
  selectedModuleId: { type: Number, default: null }
})

const emit = defineEmits(['select', 'create-case', 'changed'])

// 目录名/文件名：只允许字母、数字、下划线、短横线
const CODE_PATTERN = /^[A-Za-z0-9_-]{1,100}$/

const loading = ref(false)
const treeData = ref([])
const expandedKeys = ref([])
const searchValue = ref('')

const modalVisible = ref(false)
const submitLoading = ref(false)
const isEdit = ref(false)
const editingId = ref(null)
const originalCode = ref('')

const formState = reactive({
  parent_id: null,
  name: '',
  code: '',
  description: '',
  sort: 0
})

const selectedKeys = computed(() => (props.selectedModuleId ? [props.selectedModuleId] : []))

// 搜索：按 name 本地过滤（保留命中节点的祖先链）
const filteredTree = computed(() => {
  const keyword = searchValue.value.trim().toLowerCase()
  if (!keyword) return treeData.value
  return filterNodes(treeData.value, keyword)
})

// 当前编辑节点是否为末级（新增时视为末级）
const isCurrentLeaf = computed(() => {
  if (!editingId.value) return true
  const node = findNode(treeData.value, editingId.value)
  return node ? node.is_leaf === true : true
})

// 路径预览：末级 => {code}.py；非末级 => {code}/
const codePreview = computed(() => {
  const code = (formState.code || '').trim()
  if (!code) return '-'
  return isCurrentLeaf.value ? `${code}.py` : `${code}/`
})

// 末级但 code 未以 test_ 开头：黄色提示，不阻断保存
const showTestPrefixHint = computed(() => {
  const code = (formState.code || '').trim()
  if (!code || !isCurrentLeaf.value) return false
  return !code.startsWith('test_')
})

// 上级模块候选：顶级模块 + 当前项目节点（排除自身与自身子孙）
const parentOptions = computed(() => {
  const excluded = new Set()
  if (isEdit.value && editingId.value) {
    const self = findNode(treeData.value, editingId.value)
    if (self) collectSubtreeIds(self, excluded)
  }
  const build = (nodes) =>
    nodes
      .filter((node) => !excluded.has(node.id))
      .map((node) => ({
        label: node.name,
        value: node.id,
        children: build(node.children || [])
      }))
  return [{ label: '顶级模块', value: 0 }, ...build(treeData.value)]
})

function filterNodes(nodes, keyword) {
  const result = []
  nodes.forEach((node) => {
    const children = filterNodes(node.children || [], keyword)
    const matched = (node.name || '').toLowerCase().includes(keyword)
    if (matched || children.length) {
      result.push({ ...node, children })
    }
  })
  return result
}

function findNode(nodes, id) {
  for (const node of nodes) {
    if (node.id === id) return node
    const found = findNode(node.children || [], id)
    if (found) return found
  }
  return null
}

function collectSubtreeIds(node, acc) {
  acc.add(node.id)
  ;(node.children || []).forEach((child) => collectSubtreeIds(child, acc))
}

// 收集所有含子节点的 key，用于默认展开整棵树
function collectExpandableKeys(nodes) {
  const keys = []
  const walk = (list) => {
    list.forEach((node) => {
      if (node.children && node.children.length) {
        keys.push(node.id)
        walk(node.children)
      }
    })
  }
  walk(nodes)
  return keys
}

// 高亮命中的关键字
function highlightParts(name) {
  const text = name || ''
  const keyword = searchValue.value.trim()
  if (!keyword) return [{ text, hit: false }]
  const lowerText = text.toLowerCase()
  const lowerKeyword = keyword.toLowerCase()
  const parts = []
  let start = 0
  while (start < text.length) {
    const index = lowerText.indexOf(lowerKeyword, start)
    if (index < 0) break
    if (index > start) parts.push({ text: text.slice(start, index), hit: false })
    parts.push({ text: text.slice(index, index + keyword.length), hit: true })
    start = index + keyword.length
  }
  if (start < text.length) parts.push({ text: text.slice(start), hit: false })
  return parts.length ? parts : [{ text, hit: false }]
}

async function loadTree() {
  if (!props.projectId) {
    treeData.value = []
    expandedKeys.value = []
    return
  }
  loading.value = true
  try {
    const res = await getModuleTree(props.projectId)
    treeData.value = res.data || []
    expandedKeys.value = collectExpandableKeys(treeData.value)
  } catch (e) {
    // 错误已由请求拦截器统一提示
    treeData.value = []
    expandedKeys.value = []
  } finally {
    loading.value = false
  }
}

function onExpand(keys) {
  expandedKeys.value = keys
}

function onSelect(_keys, info) {
  const node = info && info.node
  if (!node || node.id === undefined || node.id === null) return
  emit('select', node.id)
}

function onCreateCase(node) {
  emit('create-case', node.id)
}

function openCreate(parentNode) {
  isEdit.value = false
  editingId.value = null
  originalCode.value = ''
  Object.assign(formState, {
    parent_id: parentNode ? parentNode.id : 0,
    name: '',
    code: '',
    description: '',
    sort: 0
  })
  modalVisible.value = true
}

function openEdit(node) {
  isEdit.value = true
  editingId.value = node.id
  originalCode.value = node.code || ''
  Object.assign(formState, {
    parent_id: node.parent_id === null || node.parent_id === undefined ? 0 : node.parent_id,
    name: node.name || '',
    code: node.code || '',
    description: node.description || '',
    sort: node.sort || 0
  })
  modalVisible.value = true
}

function handleSubmit() {
  const name = (formState.name || '').trim()
  const code = (formState.code || '').trim()
  if (!name) {
    message.warning('请输入模块名称')
    return
  }
  if (name.includes('/')) {
    message.warning('模块名称不能包含 /')
    return
  }
  if (name.length > 50) {
    message.warning('模块名称长度不能超过 50')
    return
  }
  if (!code) {
    message.warning('请输入目录名 / 文件名')
    return
  }
  if (!CODE_PATTERN.test(code)) {
    message.warning('只允许字母、数字、下划线、短横线，长度 1-100')
    return
  }
  if ((formState.description || '').length > 500) {
    message.warning('描述长度不能超过 500')
    return
  }
  // 编辑时修改了磁盘名：旧文件不会自动搬迁，保存前二次确认
  if (isEdit.value && originalCode.value && code !== originalCode.value) {
    Modal.confirm({
      title: '确认修改目录名 / 文件名？',
      content: '修改磁盘名不会自动搬迁磁盘上已有的文件，旧路径下的文件需要你手动清理。确定继续？',
      okText: '确定继续',
      cancelText: '取消',
      onOk: () => doSubmit(code)
    })
    return
  }
  doSubmit(code)
}

async function doSubmit(code) {
  submitLoading.value = true
  try {
    const payload = {
      name: (formState.name || '').trim(),
      code,
      description: formState.description || null,
      sort: formState.sort || 0,
      parent_id: formState.parent_id ? formState.parent_id : null
    }
    if (isEdit.value) {
      await updateModule(editingId.value, payload)
      message.success('更新成功')
    } else {
      await createModule({ project_id: props.projectId, ...payload })
      message.success('创建成功')
    }
    modalVisible.value = false
    await loadTree()
    emit('changed')
  } catch (e) {
    // 错误已由请求拦截器统一提示
  } finally {
    submitLoading.value = false
  }
}

async function handleDelete(node) {
  try {
    await deleteModule(node.id)
    message.success('删除成功')
    // 删掉的正是当前选中模块时，通知父组件清空模块筛选
    if (props.selectedModuleId === node.id) emit('select', null)
    await loadTree()
    emit('changed')
  } catch (err) {
    // 后端 409 时会在 message 中提示剩余子模块/用例数量，原样展示
    const msg = (err && err.response && err.response.data && err.response.data.message) || (err && err.message)
    if (msg) message.error(msg)
  }
}

watch(
  () => props.projectId,
  () => {
    searchValue.value = ''
    loadTree()
  }
)

watch(searchValue, (value) => {
  if (value && value.trim()) {
    expandedKeys.value = collectExpandableKeys(filteredTree.value)
  }
})

onMounted(loadTree)
</script>

<style scoped>
.tree-header {
  margin-bottom: 8px;
}
.create-root-btn {
  margin-top: 8px;
}
/* 侧栏只有 260px：必须让每一层都能被压缩。flex 子项默认 min-width: auto，
   会按「文字完整宽度」撑开（文字是 nowrap 时尤其明显），导致
   text-overflow: ellipsis 永远不触发、直接把侧栏顶破。 */
.module-tree :deep(.ant-tree-treenode) {
  display: flex;
  /* 保持 antd 默认的 flex-start，避免 show-line 的竖线高度算错 */
  align-items: flex-start;
  width: 100%;
  box-sizing: border-box;
}
.module-tree :deep(.ant-tree-node-content-wrapper) {
  flex: 1;
  min-width: 0;
  overflow: hidden;
}
.module-tree :deep(.ant-tree-title) {
  display: block;
  width: 100%;
  min-width: 0;
}
.node-title {
  display: flex;
  align-items: center;
  width: 100%;
}
/* a-tooltip 若额外包了一层，这一层同样要可收缩 */
.node-title > :first-child {
  flex: 1;
  min-width: 0;
}
.node-name {
  display: block;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.node-tail {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: none;
}
.node-actions {
  visibility: hidden;
}
.node-title:hover .node-actions {
  visibility: visible;
}
.node-icon {
  color: rgba(0, 0, 0, 0.45);
  cursor: pointer;
}
.node-icon:hover {
  color: #1677ff;
}
.node-icon-danger:hover {
  color: #ff4d4f;
}
.keyword-hit {
  color: #f5222d;
  font-weight: 600;
}
.tree-empty {
  padding: 24px 0;
}
.readonly-text {
  color: rgba(0, 0, 0, 0.65);
}
.code-preview {
  margin-top: 4px;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
}
.code-hint {
  margin-top: 4px;
  font-size: 12px;
  color: #faad14;
}
</style>
