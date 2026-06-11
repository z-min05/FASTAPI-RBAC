<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <SafetyOutlined class="login-icon" />
        <h1>RBAC 管理系统</h1>
        <p>基于角色的访问控制管理平台</p>
      </div>
      <a-form
        :model="formState"
        :rules="rules"
        @finish="handleLogin"
        class="login-form"
      >
        <a-form-item name="username">
          <a-input
            v-model:value="formState.username"
            size="large"
            placeholder="用户名"
            autocomplete="username"
          >
            <template #prefix>
              <UserOutlined style="color: rgba(0, 0, 0, 0.25)" />
            </template>
          </a-input>
        </a-form-item>
        <a-form-item name="password">
          <a-input-password
            v-model:value="formState.password"
            size="large"
            placeholder="密码"
            autocomplete="current-password"
          >
            <template #prefix>
              <LockOutlined style="color: rgba(0, 0, 0, 0.25)" />
            </template>
          </a-input-password>
        </a-form-item>
        <a-form-item name="captchaCode">
          <div class="captcha-row">
            <a-input
              v-model:value="formState.captchaCode"
              size="large"
              placeholder="验证码"
              class="captcha-input"
            >
              <template #prefix>
                <SafetyCertificateOutlined style="color: rgba(0, 0, 0, 0.25)" />
              </template>
            </a-input>
            <img
              :src="captchaImage"
              alt="验证码"
              class="captcha-img"
              @click="refreshCaptcha"
              title="点击刷新验证码"
            />
          </div>
        </a-form-item>
        <a-form-item>
          <a-button
            type="primary"
            html-type="submit"
            size="large"
            :loading="loading"
            block
          >
            登录
          </a-button>
        </a-form-item>
      </a-form>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { UserOutlined, LockOutlined, SafetyOutlined, SafetyCertificateOutlined } from '@ant-design/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { getCaptcha } from '@/api/auth'

const authStore = useAuthStore()
const loading = ref(false)
const captchaKey = ref('')
const captchaImage = ref('')

const formState = reactive({
  username: '',
  password: '',
  captchaCode: ''
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  captchaCode: [{ required: true, message: '请输入验证码', trigger: 'blur' }]
}

async function refreshCaptcha() {
  try {
    const res = await getCaptcha()
    captchaKey.value = res.data.captcha_key
    captchaImage.value = res.data.captcha_image
  } catch (e) {
    message.error('获取验证码失败')
  }
}

async function handleLogin() {
  loading.value = true
  try {
    await authStore.login(formState.username, formState.password, captchaKey.value, formState.captchaCode)
    message.success('登录成功')
  } catch (e) {
    refreshCaptcha()
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  refreshCaptcha()
})
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-card {
  width: 400px;
  padding: 40px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-icon {
  font-size: 48px;
  color: #1677ff;
  margin-bottom: 16px;
}

.login-header h1 {
  font-size: 24px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.85);
  margin: 0 0 8px;
}

.login-header p {
  color: rgba(0, 0, 0, 0.45);
  margin: 0;
  font-size: 14px;
}

.login-form {
  margin-top: 24px;
}

.captcha-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.captcha-input {
  flex: 1;
}

.captcha-img {
  height: 40px;
  cursor: pointer;
  border-radius: 4px;
  border: 1px solid #d9d9d9;
  flex-shrink: 0;
}
</style>
