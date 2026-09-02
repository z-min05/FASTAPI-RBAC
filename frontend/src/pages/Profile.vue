<template>
  <div class="profile-page">
    <a-row :gutter="24">
      <a-col :span="8">
        <a-card title="个人信息" class="info-card">
          <div class="avatar-section">
            <a-avatar :size="80" style="background-color: #1677ff; font-size: 32px">
              <template #icon><UserOutlined /></template>
            </a-avatar>
            <h3 class="user-name">{{ userInfo?.nickname || userInfo?.username || '-' }}</h3>
            <a-tag :color="userInfo?.is_superuser ? 'red' : 'blue'">
              {{ userInfo?.is_superuser ? '超级管理员' : '普通用户' }}
            </a-tag>
          </div>
          <a-descriptions :column="1" size="small" bordered>
            <a-descriptions-item label="用户名">{{ userInfo?.username || '-' }}</a-descriptions-item>
            <a-descriptions-item label="昵称">{{ userInfo?.nickname || '-' }}</a-descriptions-item>
            <a-descriptions-item label="邮箱">{{ userInfo?.email || '-' }}</a-descriptions-item>
          </a-descriptions>
        </a-card>
      </a-col>
      <a-col :span="16">
        <a-card title="修改信息" class="edit-card">
          <a-form :model="formState" :label-col="{ span: 4 }" :wrapper-col="{ span: 18 }" @finish="handleUpdateInfo">
            <a-form-item label="昵称" name="nickname">
              <a-input v-model:value="formState.nickname" placeholder="请输入昵称" />
            </a-form-item>
            <a-form-item label="邮箱" name="email">
              <a-input v-model:value="formState.email" placeholder="请输入邮箱" />
            </a-form-item>
            <a-form-item label="手机号" name="phone">
              <a-input v-model:value="formState.phone" placeholder="请输入手机号" />
            </a-form-item>
            <a-form-item :wrapper-col="{ offset: 4, span: 18 }">
              <a-button type="primary" html-type="submit" :loading="infoLoading">保存修改</a-button>
            </a-form-item>
          </a-form>
        </a-card>
        <a-card title="修改密码" class="edit-card" style="margin-top: 16px">
          <a-form :model="pwdState" :label-col="{ span: 4 }" :wrapper-col="{ span: 18 }" @finish="handleUpdatePwd">
            <a-form-item label="当前密码" name="old_password" :rules="[{ required: true, message: '请输入当前密码' }]">
              <a-input-password v-model:value="pwdState.old_password" placeholder="请输入当前密码" />
            </a-form-item>
            <a-form-item label="新密码" name="new_password" :rules="[{ required: true, min: 6, message: '密码至少6位' }]">
              <a-input-password v-model:value="pwdState.new_password" placeholder="请输入新密码" />
            </a-form-item>
            <a-form-item label="确认密码" name="confirm_password" :rules="[{ required: true, message: '请确认新密码' }, { validator: validateConfirmPwd }]">
              <a-input-password v-model:value="pwdState.confirm_password" placeholder="请再次输入新密码" />
            </a-form-item>
            <a-form-item :wrapper-col="{ offset: 4, span: 18 }">
              <a-button type="primary" html-type="submit" :loading="pwdLoading">修改密码</a-button>
            </a-form-item>
          </a-form>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { UserOutlined } from '@ant-design/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { updateUser, changePassword } from '@/api/user'

const authStore = useAuthStore()
const userInfo = ref(authStore.userInfo || {})
const infoLoading = ref(false)
const pwdLoading = ref(false)

const formState = reactive({
  nickname: '',
  email: '',
  phone: ''
})

const pwdState = reactive({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

function validateConfirmPwd(_rule, value) {
  if (value && value !== pwdState.new_password) {
    return Promise.reject('两次输入的密码不一致')
  }
  return Promise.resolve()
}

onMounted(async () => {
  if (!authStore.userInfo) {
    await authStore.fetchUserInfo()
  }
  userInfo.value = authStore.userInfo || {}
  formState.nickname = userInfo.value.nickname || ''
  formState.email = userInfo.value.email || ''
  formState.phone = userInfo.value.phone || ''
})

async function handleUpdateInfo() {
  infoLoading.value = true
  try {
    await updateUser(userInfo.value.id, formState)
    message.success('信息更新成功')
    await authStore.fetchUserInfo()
    userInfo.value = authStore.userInfo || {}
  } catch (e) {
    message.error(e.response?.data?.message || '更新失败')
  } finally {
    infoLoading.value = false
  }
}

async function handleUpdatePwd() {
  pwdLoading.value = true
  try {
    await changePassword(userInfo.value.id, {
      old_password: pwdState.old_password,
      new_password: pwdState.new_password
    })
    message.success('密码修改成功，请重新登录')
    authStore.logout()
  } catch (e) {
    message.error(e.response?.data?.message || '修改失败')
  } finally {
    pwdLoading.value = false
  }
}
</script>

<style scoped>
.profile-page {
  max-width: 1000px;
}

.avatar-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.user-name {
  margin: 0;
  font-size: 18px;
}
</style>
