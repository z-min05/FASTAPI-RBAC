<template>
  <a-layout style="min-height: 100vh">
    <a-layout-sider
      v-model:collapsed="appStore.collapsed"
      collapsible
      :trigger="null"
      theme="dark"
      :width="220"
    >
      <div class="logo">
        <SafetyOutlined style="font-size: 24px" />
        <span v-if="!appStore.collapsed" class="logo-text">RBAC 管理系统</span>
      </div>
      <a-menu
        v-model:selectedKeys="selectedKeys"
        v-model:openKeys="openKeys"
        theme="dark"
        mode="inline"
        @click="onMenuClick"
      >
        <template v-for="menu in menuList" :key="menu.path || menu.id">
          <!-- 目录类型：有子菜单 -->
          <a-sub-menu v-if="menu.children && menu.children.length" :key="String(menu.id)">
            <template #title>
              <component :is="iconMap[menu.icon]" v-if="menu.icon && iconMap[menu.icon]" />
              <span>{{ menu.name }}</span>
            </template>
            <a-menu-item
              v-for="child in menu.children"
              :key="child.path"
            >
              <component :is="iconMap[child.icon]" v-if="child.icon && iconMap[child.icon]" />
              <span>{{ child.name }}</span>
            </a-menu-item>
          </a-sub-menu>
          <!-- 菜单类型：无子菜单 -->
          <a-menu-item v-else :key="menu.path">
            <component :is="iconMap[menu.icon]" v-if="menu.icon && iconMap[menu.icon]" />
            <span>{{ menu.name }}</span>
          </a-menu-item>
        </template>
      </a-menu>
    </a-layout-sider>

    <a-layout>
      <a-layout-header class="header">
        <div class="header-left">
          <MenuFoldOutlined
            v-if="!appStore.collapsed"
            class="trigger"
            @click="appStore.toggleCollapsed"
          />
          <MenuUnfoldOutlined
            v-else
            class="trigger"
            @click="appStore.toggleCollapsed"
          />
          <a-breadcrumb class="breadcrumb">
            <a-breadcrumb-item>
              <router-link to="/">首页</router-link>
            </a-breadcrumb-item>
            <a-breadcrumb-item v-if="currentRoute.meta?.title">
              {{ currentRoute.meta.title }}
            </a-breadcrumb-item>
          </a-breadcrumb>
        </div>
        <div class="header-right">
          <a-tooltip title="数据大屏">
            <a class="bigscreen-btn" @click="$router.push('/bigscreen')">
              <FundOutlined style="font-size: 18px" />
            </a>
          </a-tooltip>
          <a-tooltip title="智慧园区大屏">
            <a class="bigscreen-btn" @click="$router.push('/smartpark')">
              <BuildOutlined style="font-size: 18px" />
            </a>
          </a-tooltip>
          <a-dropdown>
            <a class="user-info" @click.prevent>
              <a-avatar :size="28" style="background-color: #1677ff">
                <template #icon><UserOutlined /></template>
              </a-avatar>
              <span class="username">Admin</span>
            </a>
            <template #overlay>
              <a-menu>
                <a-menu-item @click="authStore.logout">
                  <LogoutOutlined />
                  退出登录
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </div>
      </a-layout-header>

      <a-layout-content class="content">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import {
  DashboardOutlined,
  SettingOutlined,
  UserOutlined,
  TeamOutlined,
  SafetyOutlined,
  MenuOutlined,
  ApartmentOutlined,
  FileTextOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  LogoutOutlined,
  HomeOutlined,
  AppstoreOutlined,
  ProfileOutlined,
  KeyOutlined,
  OrderedListOutlined,
  PartitionOutlined,
  FileSearchOutlined,
  FundOutlined,
  BuildOutlined
} from '@ant-design/icons-vue'

const router = useRouter()
const route = useRoute()
const appStore = useAppStore()
const authStore = useAuthStore()

// 图标名称到组件的映射
const iconMap = {
  DashboardOutlined,
  SettingOutlined,
  UserOutlined,
  TeamOutlined,
  SafetyOutlined,
  MenuOutlined,
  ApartmentOutlined,
  FileTextOutlined,
  HomeOutlined,
  AppstoreOutlined,
  ProfileOutlined,
  KeyOutlined,
  OrderedListOutlined,
  PartitionOutlined,
  FileSearchOutlined
}

const currentRoute = computed(() => route)
const selectedKeys = ref([route.path])
const openKeys = ref([])

// 从 auth store 获取菜单，过滤掉按钮类型
const menuList = computed(() => {
  return (authStore.menus || []).filter(m => m.menu_type !== 'button')
})

// 计算需要展开的目录 key
function collectOpenKeys(menus) {
  const keys = []
  for (const menu of menus) {
    if (menu.children && menu.children.length) {
      keys.push(String(menu.id))
    }
  }
  return keys
}

watch(
  () => route.path,
  (path) => {
    selectedKeys.value = [path]
    openKeys.value = collectOpenKeys(menuList.value)
  }
)

watch(menuList, () => {
  openKeys.value = collectOpenKeys(menuList.value)
}, { immediate: true })

function onMenuClick({ key }) {
  if (key.startsWith('/')) {
    router.push(key)
  }
}

onMounted(async () => {
  if (authStore.isLoggedIn && authStore.menus.length === 0) {
    await authStore.fetchMenus()
  }
})
</script>

<style scoped>
.logo {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.logo-text {
  white-space: nowrap;
  overflow: hidden;
}

.header {
  background: #fff;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  height: 64px;
  line-height: 64px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.trigger {
  font-size: 18px;
  cursor: pointer;
  transition: color 0.3s;
}

.trigger:hover {
  color: #1677ff;
}

.breadcrumb {
  line-height: 64px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.bigscreen-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 6px;
  color: rgba(0, 0, 0, 0.65);
  transition: all 0.3s;
}

.bigscreen-btn:hover {
  background: rgba(22, 119, 255, 0.08);
  color: #1677ff;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  color: rgba(0, 0, 0, 0.85);
}

.username {
  font-size: 14px;
}

.content {
  margin: 24px;
  padding: 24px;
  background: #fff;
  border-radius: 8px;
  min-height: 280px;
}
</style>
