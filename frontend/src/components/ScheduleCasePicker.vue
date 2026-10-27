<template>
  <a-modal
    :open="open"
    title="选择用例"
    :footer="null"
    width="1080px"
    @cancel="handleCancel"
  >
    <!-- 筛选区：优先级 / 标签 / 关键字 -->
    <div class="picker-toolbar">
      <a-space :wrap="true">
        <a-select
          v-model:value="priorityFilter"
          placeholder="优先级"
          style="width: 110px"
          :options="priorityOptions"
          allow-clear
        />
        <a-select
          v-model:value="tagFilter"
          placeholder="标签"
          style="width: 170px"
          :options="tagOptions"
          allow-clear
          show-search
          option-filter-prop="label"
        />
        <a-input-search
          v-model:value="keyword"
          placeholder="搜索用例标题/模块/编号"
          style="width: 240px"
          allow-clear
        />
        <a-button size="small" :disabled="!hasFilter" @click="clearFilters">清空筛选</a-button>
      </a-space>
      <a-space :wrap="false">
        <a-button size="small" :disabled="!filteredCandidates.length" @click="selectAllFiltered">
          全选筛选结果
        </a-button>
        <a-button size="small" :disabled="!selectedKeys.length" @click="clearSelection">取消选择</a-button>
        <span class="selected-tip">已选 {{ selectedKeys.length }} 条</span>
      </a-space>
    </div>

    <!-- 左侧模块树（含子模块）+ 右侧用例表格 -->
    <div class="picker-body">
      <div v-if="canViewModuleTree" class="picker-module-panel">
        <TestcaseModuleTree
          :project-id="projectId"
          filter-only
          :selected-module-id="moduleFilter"
          @select="onModuleSelect"
          @loaded="onTreeLoaded"
        />
      </div>
      <div class="picker-table-panel">
        <a-table
          :columns="columns"
          :data-source="pagedCandidates"
          :loading="loading"
          :pagination="pagination"
          :row-selection="rowSelection"
          row-key="testcase_id"
          size="small"
          :scroll="TABLE_SCROLL_MODAL(columns)"
          table-layout="fixed"
          @change="handleTableChange"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'code'">
              {{ caseCode(record) }}
            </template>
            <template v-else-if="column.key === 'priority'">
              <a-tag :color="priorityColor(record.priority)">{{ record.priority || '-' }}</a-tag>
            </template>
          </template>
        </a-table>
      </div>
    </div>

    <div class="picker-footer">
      <span class="picker-footer-tip">共 {{ filteredCandidates.length }} 条可勾选</span>
      <a-space>
        <a-button @click="handleCancel">取消</a-button>
        <a-button type="primary" :disabled="!selectedKeys.length" @click="handleOk">
          确定（{{ selectedKeys.length }}）
        </a-button>
      </a-space>
    </div>
  </a-modal>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import TestcaseModuleTree from '@/components/TestcaseModuleTree.vue'
import { hasAnyPermission } from '@/utils/permission'
import { TABLE_SCROLL_MODAL } from '@/utils/tableScroll'

const props = defineProps({
  open: { type: Boolean, default: false },
  /** 计划所属项目 ID：用于加载模块树 */
  projectId: { type: Number, required: true },
  /** 可自动化的计划用例全量数据（父级已加载，避免重复请求） */
  candidates: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  /** 已选用例 ID 列表（testcase_id） */
  modelValue: { type: Array, default: () => [] }
})

const emit = defineEmits(['update:open', 'update:modelValue'])

const columns = [
  { title: '用例编号', key: 'code', width: 150, ellipsis: true },
  { title: '用例标题', dataIndex: 'title', key: 'title', width: 240, ellipsis: true },
  { title: '模块', dataIndex: 'module', key: 'module', width: 130, ellipsis: true },
  { title: '优先级', dataIndex: 'priority', key: 'priority', width: 84 },
  { title: '标签', dataIndex: 'tags', key: 'tags', width: 160, ellipsis: true }
]

// ---------- 筛选条件 ----------
const keyword = ref('')
const priorityFilter = ref(null)
const tagFilter = ref(null)
const moduleFilter = ref(null)

// ---------- 勾选（暂存，点「确定」才回写父级） ----------
const selectedKeys = ref([])

// ---------- 分页（前端分页，筛选结果内翻页） ----------
const page = ref(1)
const pageSize = ref(10)

// 模块树数据：用于把「选中模块」展开为其子树 ID 集合
const moduleTreeData = ref([])

// 模块树接口复用 testcase:list 读权限；无权限的账号隐藏左侧模块筛选
const canViewModuleTree = computed(() => hasAnyPermission(['testcase:list']))

const priorityOptions = computed(() => {
  const set = new Set()
  props.candidates.forEach((t) => {
    if (t.priority) set.add(t.priority)
  })
  return [...set].sort().map((p) => ({ label: p, value: p }))
})

const tagOptions = computed(() => {
  const set = new Set()
  props.candidates.forEach((t) => {
    splitTags(t.tags).forEach((tag) => set.add(tag))
  })
  return [...set].sort().map((tag) => ({ label: tag, value: tag }))
})

const hasFilter = computed(
  () => !!keyword.value || !!priorityFilter.value || !!tagFilter.value || !!moduleFilter.value
)

// 选中模块（含全部子模块）对应的模块 ID 集合；未选模块时为 null（不过滤）
const moduleIdSet = computed(() => {
  const id = moduleFilter.value
  if (!id) return null
  const node = findNode(moduleTreeData.value, id)
  if (!node) return new Set([id])
  const set = new Set()
  collectSubtreeIds(node, set)
  return set
})

const filteredCandidates = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  const priority = priorityFilter.value
  const tag = tagFilter.value
  const moduleIds = moduleIdSet.value
  return props.candidates.filter((t) => {
    if (priority && (t.priority || '') !== priority) return false
    if (tag && !splitTags(t.tags).includes(tag)) return false
    if (moduleIds && !moduleIds.has(t.module_id)) return false
    if (kw) {
      const haystack = [
        t.title,
        t.module,
        t.module_code,
        t.case_code
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      if (!haystack.includes(kw)) return false
    }
    return true
  })
})

const pagedCandidates = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredCandidates.value.slice(start, start + pageSize.value)
})

const pagination = computed(() => ({
  current: page.value,
  pageSize: pageSize.value,
  total: filteredCandidates.value.length,
  showSizeChanger: true,
  pageSizeOptions: ['10', '20', '50', '100'],
  showTotal: (total) => `共 ${total} 条`
}))

const rowSelection = computed(() => ({
  selectedRowKeys: selectedKeys.value,
  preserveSelectedRowKeys: true,
  onChange: (keys) => {
    selectedKeys.value = keys
  }
}))

function splitTags(tags) {
  if (!tags) return []
  return String(tags)
    .split(/[,，、;；]/)
    .map((t) => t.trim())
    .filter(Boolean)
}

function caseCode(record) {
  if (!record.module_code && !record.case_code) return '-'
  return `${record.module_code || '-'} / ${record.case_code || '-'}`
}

function priorityColor(p) {
  return { P0: 'red', P1: 'orange', P2: 'blue', P3: 'default' }[p] || 'default'
}

function collectSubtreeIds(node, acc) {
  acc.add(node.id)
  ;(node.children || []).forEach((child) => collectSubtreeIds(child, acc))
}

function findNode(nodes, id) {
  for (const node of nodes) {
    if (node.id === id) return node
    const found = findNode(node.children || [], id)
    if (found) return found
  }
  return null
}

// ---------- 交互 ----------
function onTreeLoaded(data) {
  moduleTreeData.value = data || []
}

// 点击模块筛选；再次点击已选模块 => 取消模块筛选（查看全部）
function onModuleSelect(moduleId) {
  moduleFilter.value = moduleId || null
}

function handleTableChange(pag) {
  page.value = pag.current
  pageSize.value = pag.pageSize
}

function clearFilters() {
  keyword.value = ''
  priorityFilter.value = null
  tagFilter.value = null
  moduleFilter.value = null
}

function clearSelection() {
  selectedKeys.value = []
}

// 全选当前筛选结果（保留已选的其他用例）
function selectAllFiltered() {
  const merged = new Set(selectedKeys.value)
  filteredCandidates.value.forEach((t) => merged.add(t.testcase_id))
  selectedKeys.value = [...merged]
}

function handleCancel() {
  emit('update:open', false)
}

function handleOk() {
  emit('update:modelValue', [...selectedKeys.value])
  emit('update:open', false)
}

// 打开时：回填已选用例并重置筛选条件
watch(
  () => props.open,
  (open) => {
    if (!open) return
    selectedKeys.value = [...(props.modelValue || [])]
    clearFilters()
    page.value = 1
  }
)

// 筛选项变化后回到第一页
watch([keyword, priorityFilter, tagFilter, moduleFilter], () => {
  page.value = 1
})

// 筛选结果变少时，避免停留在超范围页码
watch(
  () => filteredCandidates.value.length,
  (len) => {
    const maxPage = Math.max(1, Math.ceil(len / pageSize.value))
    if (page.value > maxPage) page.value = maxPage
  }
)
</script>

<style scoped>
.picker-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}
.selected-tip {
  color: #1677ff;
  font-size: 13px;
  white-space: nowrap;
}
.picker-body {
  display: flex;
  gap: 12px;
}
/* 模块面板：固定高度与右侧表格（TABLE_SCROLL_MODAL 表体 420px + 表头 + 分页）对齐 */
.picker-module-panel {
  flex: 0 0 240px;
  width: 240px;
  min-width: 0;
  height: 523px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 8px;
  border: 1px solid #f0f0f0;
  border-radius: 4px;
  box-sizing: border-box;
}
.picker-table-panel {
  flex: 1;
  min-width: 0;
}
.picker-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
}
.picker-footer-tip {
  color: rgba(0, 0, 0, 0.45);
  font-size: 13px;
}
/* 小屏幕下隐藏模块树，保证表格可用 */
@media (max-width: 991px) {
  .picker-module-panel {
    display: none;
  }
}
</style>
