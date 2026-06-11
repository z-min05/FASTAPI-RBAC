<template>
  <div class="dashboard">
    <a-row :gutter="[24, 24]">
      <a-col :span="6">
        <a-card class="stat-card" :bordered="false">
          <div class="stat-icon" style="background: #e6f7ff">
            <UserOutlined style="color: #1677ff; font-size: 28px" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.userCount }}</div>
            <div class="stat-label">用户总数</div>
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="stat-card" :bordered="false">
          <div class="stat-icon" style="background: #f6ffed">
            <TeamOutlined style="color: #52c41a; font-size: 28px" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.roleCount }}</div>
            <div class="stat-label">角色总数</div>
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="stat-card" :bordered="false">
          <div class="stat-icon" style="background: #fff7e6">
            <SafetyOutlined style="color: #faad14; font-size: 28px" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.permCount }}</div>
            <div class="stat-label">权限总数</div>
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="stat-card" :bordered="false">
          <div class="stat-icon" style="background: #fff1f0">
            <ApartmentOutlined style="color: #ff4d4f; font-size: 28px" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.deptCount }}</div>
            <div class="stat-label">部门总数</div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <a-row :gutter="24" style="margin-top: 24px">
      <a-col :span="16">
        <a-card title="系统信息" :bordered="false">
          <a-descriptions :column="2" bordered size="small">
            <a-descriptions-item label="系统名称">RBAC 管理系统</a-descriptions-item>
            <a-descriptions-item label="系统版本">1.0.0</a-descriptions-item>
            <a-descriptions-item label="前端框架">Vue 3 + Ant Design Vue</a-descriptions-item>
            <a-descriptions-item label="后端框架">FastAPI</a-descriptions-item>
            <a-descriptions-item label="数据库">PostgreSQL</a-descriptions-item>
            <a-descriptions-item label="缓存">Redis</a-descriptions-item>
          </a-descriptions>
        </a-card>
      </a-col>
      <a-col :span="8">
        <a-card title="快捷操作" :bordered="false">
          <a-space direction="vertical" style="width: 100%">
            <a-button type="primary" block @click="$router.push('/system/users')">
              <UserOutlined /> 用户管理
            </a-button>
            <a-button block @click="$router.push('/system/roles')">
              <TeamOutlined /> 角色管理
            </a-button>
            <a-button block @click="$router.push('/system/permissions')">
              <SafetyOutlined /> 权限管理
            </a-button>
            <a-button block @click="$router.push('/system/logs')">
              <FileTextOutlined /> 操作日志
            </a-button>
          </a-space>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup>
import { reactive, onMounted } from 'vue'
import { UserOutlined, TeamOutlined, SafetyOutlined, ApartmentOutlined, FileTextOutlined } from '@ant-design/icons-vue'
import { getUsers } from '@/api/user'
import { getRoles } from '@/api/role'
import { getPermissions } from '@/api/permission'
import { getDepartments } from '@/api/department'

const stats = reactive({
  userCount: 0,
  roleCount: 0,
  permCount: 0,
  deptCount: 0
})

onMounted(async () => {
  try {
    const [users, roles, perms, depts] = await Promise.all([
      getUsers({ page: 1, page_size: 1 }),
      getRoles({ page: 1, page_size: 1 }),
      getPermissions({ page: 1, page_size: 1 }),
      getDepartments({ page: 1, page_size: 1 })
    ])
    stats.userCount = users.data.total || 0
    stats.roleCount = roles.data.total || 0
    stats.permCount = perms.data.total || 0
    stats.deptCount = depts.data.total || 0
  } catch (e) {
    // 静默处理
  }
})
</script>

<style scoped>
.stat-card {
  display: flex;
  align-items: center;
}

.stat-card :deep(.ant-card-body) {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 24px;
  width: 100%;
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.85);
  line-height: 1.2;
}

.stat-label {
  font-size: 14px;
  color: rgba(0, 0, 0, 0.45);
  margin-top: 4px;
}
</style>
