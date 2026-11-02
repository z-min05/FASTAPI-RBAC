<template>
  <div>
    <div class="page-header">
      <a-space>
        <a-input-search
          v-model:value="searchText"
          placeholder="搜索工具名称"
          style="width: 240px"
          @search="handleSearch"
          allow-clear
        />
        <a-button @click="handleReset">重置</a-button>
        <a-button type="primary" @click="showUploadModal" v-permission="'tool:create'">
          <UploadOutlined /> 上传工具
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
      :scroll="TABLE_SCROLL(columns)"
      table-layout="fixed"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'name'">
          <a @click="showDetail(record)">{{ record.name }}</a>
        </template>
        <template v-if="column.key === 'package'">
          {{ record.package_filename }}
        </template>
        <template v-if="column.key === 'package_size'">
          {{ formatSize(record.package_size) }}
        </template>
        <template v-if="column.key === 'readme'">
          {{ record.readme_filename }}
        </template>
        <template v-if="column.key === 'created_at'">
          {{ formatDate(record.created_at) }}
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="showDetail(record)">详情</a-button>
            <a-button
              type="link"
              size="small"
              v-permission="'tool:download'"
              :loading="downloadingId === record.id"
              @click="handleDownload(record)"
            >下载</a-button>
            <a-popconfirm
              title="删除该工具？数据库记录与磁盘上的压缩包、README 文件都会被删除，且不可恢复。"
              ok-text="删除"
              @confirm="handleDelete(record.id)"
            >
              <a-button type="link" size="small" danger v-permission="'tool:delete'">删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 上传工具 -->
    <a-modal
      v-model:open="uploadVisible"
      title="上传工具"
      @ok="handleUpload"
      :confirm-loading="uploading"
      ok-text="上传"
      width="620px"
    >
      <a-form :model="formState" ref="formRef" :rules="formRules" :label-col="{ span: 4 }" :wrapper-col="{ span: 19 }">
        <a-form-item name="name" label="工具名称" required>
          <a-input v-model:value="formState.name" placeholder="请输入工具名称" :maxlength="200" />
        </a-form-item>
        <a-form-item name="description" label="工具描述">
          <a-textarea v-model:value="formState.description" :rows="3" placeholder="工具用途说明（选填）" />
        </a-form-item>
        <a-form-item label="压缩包" required>
          <a-upload-dragger :show-upload-list="false" accept=".zip" :before-upload="beforeUploadPackage">
            <p class="ant-upload-drag-icon"><InboxOutlined /></p>
            <p class="ant-upload-text">点击或拖拽 .zip 压缩包到此处</p>
          </a-upload-dragger>
          <div class="form-hint" v-if="packageFile">
            <span>已选择：{{ packageFile.name }}（{{ formatSize(packageFile.size) }}）</span>
            <a @click="packageFile = null">移除</a>
          </div>
        </a-form-item>
        <a-form-item label="README" required>
          <a-upload-dragger :show-upload-list="false" accept=".md" :before-upload="beforeUploadReadme">
            <p class="ant-upload-drag-icon"><FileMarkdownOutlined /></p>
            <p class="ant-upload-text">点击或拖拽 README.md 文档到此处</p>
          </a-upload-dragger>
          <div class="form-hint" v-if="readmeFile">
            <span>已选择：{{ readmeFile.name }}（{{ formatSize(readmeFile.size) }}）</span>
            <a @click="readmeFile = null">移除</a>
          </div>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 工具详情 -->
    <a-modal
      v-model:open="detailVisible"
      :title="detail.name || '工具详情'"
      :footer="null"
      width="860px"
      wrap-class-name="tool-detail-modal"
    >
      <a-spin :spinning="detailLoading">
        <a-descriptions :column="2" size="small" bordered>
          <a-descriptions-item label="工具名称" :span="2">{{ detail.name }}</a-descriptions-item>
          <a-descriptions-item label="压缩包">{{ detail.package_filename }}</a-descriptions-item>
          <a-descriptions-item label="压缩包大小">{{ formatSize(detail.package_size) }}</a-descriptions-item>
          <a-descriptions-item label="上传人">{{ detail.created_by_name || '-' }}</a-descriptions-item>
          <a-descriptions-item label="上传时间">{{ formatDate(detail.created_at) }}</a-descriptions-item>
          <a-descriptions-item label="描述" :span="2">{{ detail.description || '-' }}</a-descriptions-item>
        </a-descriptions>

        <div class="readme-header">
          <span>README：{{ detail.readme_filename }}</span>
          <a-space>
            <a-button
              size="small"
              v-permission="'tool:download'"
              :loading="detailDownloading"
              @click="handleDownload(detail)"
            >
              <DownloadOutlined /> 下载压缩包
            </a-button>
            <a-popconfirm
              title="删除该工具？数据库记录与磁盘文件都会被删除，且不可恢复。"
              ok-text="删除"
              @confirm="handleDelete(detail.id)"
            >
              <a-button
                size="small"
                danger
                v-permission="'tool:delete'"
              >删除</a-button>
            </a-popconfirm>
          </a-space>
        </div>
        <div v-if="readmeHtml" class="markdown-body" v-html="readmeHtml"></div>
        <div v-else class="readme-empty">（无 README 内容）</div>
      </a-spin>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { UploadOutlined, InboxOutlined, FileMarkdownOutlined, DownloadOutlined } from '@ant-design/icons-vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { getTools, getTool, createTool, downloadToolPackage, deleteTool } from '@/api/tool'
import { TABLE_SCROLL } from '@/utils/tableScroll'
import dayjs from 'dayjs'

const loading = ref(false)
const searchText = ref('')

const tableData = ref([])
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  pageSizeOptions: ['10', '20', '50', '100']
})

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
  { title: '工具名称', dataIndex: 'name', key: 'name', width: 200, ellipsis: true },
  { title: '描述', dataIndex: 'description', key: 'description', width: 260, ellipsis: true },
  { title: '压缩包', dataIndex: 'package_filename', key: 'package', width: 220, ellipsis: true },
  { title: '大小', dataIndex: 'package_size', key: 'package_size', width: 100 },
  { title: 'README', dataIndex: 'readme_filename', key: 'readme', width: 180, ellipsis: true },
  { title: '上传人', dataIndex: 'created_by_name', key: 'created_by_name', width: 120, ellipsis: true },
  { title: '上传时间', dataIndex: 'created_at', key: 'created_at', width: 160 },
  { title: '操作', key: 'action', width: 180, fixed: 'right' }
]

function formatDate(val) {
  return val ? dayjs(val).format('YYYY-MM-DD HH:mm') : '-'
}

function formatSize(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let i = 0
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024
    i++
  }
  return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

async function loadData() {
  loading.value = true
  try {
    const params = { page: pagination.current, page_size: pagination.pageSize }
    if (searchText.value) params.keyword = searchText.value
    const res = await getTools(params)
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
  pagination.current = 1
  loadData()
}

// ---------- 上传 ----------
const uploadVisible = ref(false)
const uploading = ref(false)
const formRef = ref(null)
const packageFile = ref(null)
const readmeFile = ref(null)
const formState = reactive({ name: '', description: '' })

const formRules = {
  name: [{ required: true, message: '请输入工具名称', trigger: 'blur' }]
}

function showUploadModal() {
  formState.name = ''
  formState.description = ''
  packageFile.value = null
  readmeFile.value = null
  formRef.value?.clearValidate()
  uploadVisible.value = true
}

function beforeUploadPackage(file) {
  if (!file.name.toLowerCase().endsWith('.zip')) {
    message.warning('压缩包仅支持 .zip 格式')
    return false
  }
  packageFile.value = file
  return false
}

function beforeUploadReadme(file) {
  if (!file.name.toLowerCase().endsWith('.md')) {
    message.warning('README 仅支持 .md 格式')
    return false
  }
  readmeFile.value = file
  return false
}

async function handleUpload() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  if (!packageFile.value) {
    message.warning('请选择 .zip 压缩包')
    return
  }
  if (!readmeFile.value) {
    message.warning('请选择 README.md 文档')
    return
  }
  uploading.value = true
  try {
    const res = await createTool({
      name: formState.name.trim(),
      description: formState.description?.trim(),
      packageFile: packageFile.value,
      readmeFile: readmeFile.value
    })
    if (res.code === 200) {
      message.success('上传成功')
      uploadVisible.value = false
      pagination.current = 1
      loadData()
    }
  } catch (e) {
    // 错误已由拦截器处理
  } finally {
    uploading.value = false
  }
}

// ---------- 详情 ----------
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailDownloading = ref(false)
const detail = reactive({
  id: null,
  name: '',
  description: '',
  package_filename: '',
  package_size: 0,
  readme_filename: '',
  readme_content: '',
  created_by_name: '',
  created_at: null
})

// README 以 Markdown 渲染；内容来自用户上传，必须经 DOMPurify 过滤后再插入
const readmeHtml = computed(() => {
  const md = detail.readme_content
  if (!md) return ''
  return DOMPurify.sanitize(marked.parse(md))
})

async function showDetail(record) {
  Object.assign(detail, {
    id: record.id,
    name: record.name,
    description: record.description,
    package_filename: record.package_filename,
    package_size: record.package_size,
    readme_filename: record.readme_filename,
    readme_content: '',
    created_by_name: record.created_by_name,
    created_at: record.created_at
  })
  detailVisible.value = true
  detailLoading.value = true
  try {
    const res = await getTool(record.id)
    if (res.code === 200 && res.data) {
      Object.assign(detail, res.data)
    }
  } catch (e) {
    // 错误已由拦截器处理
  } finally {
    detailLoading.value = false
  }
}

// ---------- 下载 ----------
const downloadingId = ref(null)

function saveBlob(blob, filename) {
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename
  link.click()
  URL.revokeObjectURL(link.href)
}

async function handleDownload(record) {
  if (!record?.id) return
  const inDetail = detailVisible.value && detail.id === record.id
  if (inDetail) detailDownloading.value = true
  else downloadingId.value = record.id
  try {
    const blob = await downloadToolPackage(record.id)
    saveBlob(blob, record.package_filename || `tool_${record.id}.zip`)
    message.success('开始下载')
  } catch (e) {
    // 错误已由拦截器处理
  } finally {
    downloadingId.value = null
    detailDownloading.value = false
  }
}

// ---------- 删除 ----------
async function handleDelete(id) {
  if (!id) return
  try {
    const res = await deleteTool(id)
    if (res.code === 200) {
      message.success('删除成功')
      if (detailVisible.value && detail.id === id) detailVisible.value = false
      if (tableData.value.length === 1 && pagination.current > 1) pagination.current -= 1
      loadData()
    }
  } catch (e) {
    // 错误已由拦截器处理
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
  display: flex;
  gap: 8px;
}
.readme-header {
  margin: 16px 0 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 500;
}
.markdown-body {
  max-height: 480px;
  overflow: auto;
  padding: 16px 20px;
  background: #fff;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  font-size: 14px;
  line-height: 1.75;
  color: rgba(0, 0, 0, 0.85);
  word-break: break-word;
}
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4),
.markdown-body :deep(h5),
.markdown-body :deep(h6) {
  margin: 20px 0 10px;
  font-weight: 600;
  line-height: 1.4;
  color: rgba(0, 0, 0, 0.88);
}
.markdown-body :deep(h1) {
  font-size: 24px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f0f0f0;
}
.markdown-body :deep(h2) {
  font-size: 20px;
  padding-bottom: 6px;
  border-bottom: 1px solid #f0f0f0;
}
.markdown-body :deep(h3) { font-size: 17px; }
.markdown-body :deep(h4) { font-size: 15px; }
.markdown-body :deep(h5),
.markdown-body :deep(h6) { font-size: 14px; }
.markdown-body :deep(p) {
  margin: 0 0 12px;
}
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0 0 12px;
  padding-left: 24px;
}
.markdown-body :deep(li) {
  margin: 4px 0;
}
.markdown-body :deep(li > p) {
  margin: 0;
}
.markdown-body :deep(a) {
  color: #1677ff;
  text-decoration: none;
}
.markdown-body :deep(a:hover) {
  text-decoration: underline;
}
.markdown-body :deep(code) {
  padding: 2px 5px;
  margin: 0 2px;
  background: rgba(0, 0, 0, 0.05);
  border-radius: 4px;
  font-family: Consolas, Monaco, 'Courier New', monospace;
  font-size: 13px;
}
.markdown-body :deep(pre) {
  margin: 0 0 12px;
  padding: 12px 14px;
  background: #f6f8fa;
  border-radius: 6px;
  overflow: auto;
}
.markdown-body :deep(pre code) {
  padding: 0;
  margin: 0;
  background: transparent;
  font-size: 13px;
  line-height: 1.6;
}
.markdown-body :deep(blockquote) {
  margin: 0 0 12px;
  padding: 4px 12px;
  color: rgba(0, 0, 0, 0.6);
  border-left: 4px solid #e6e6e6;
  background: #fafafa;
}
.markdown-body :deep(table) {
  width: 100%;
  margin: 0 0 12px;
  border-collapse: collapse;
}
.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: 6px 10px;
  border: 1px solid #f0f0f0;
  text-align: left;
}
.markdown-body :deep(th) {
  background: #fafafa;
  font-weight: 600;
}
.markdown-body :deep(img) {
  max-width: 100%;
}
.markdown-body :deep(hr) {
  height: 1px;
  margin: 16px 0;
  border: none;
  background: #f0f0f0;
}
.readme-empty {
  padding: 24px;
  text-align: center;
  color: #999;
  background: #fafafa;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
}
</style>
