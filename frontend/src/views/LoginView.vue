<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { errorMessage } from '@/lib/api'
import { login } from '@/lib/auth'

const route = useRoute()
const router = useRouter()

const name = ref('')
const studentId = ref('')
const password = ref('')
const busy = ref(false)
const error = ref('')

async function onSubmit() {
  if (busy.value) return
  error.value = ''
  busy.value = true
  try {
    const profile = await login(name.value, studentId.value, password.value)
    if (profile.must_change_password) {
      await router.replace({ name: 'change-password' })
      return
    }
    const next = typeof route.query.next === 'string' && route.query.next.startsWith('/') ? route.query.next : '/home'
    await router.replace(next)
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="page page-narrow">
    <form class="card stack" @submit.prevent="onSubmit">
      <div>
        <h1>로그인</h1>
        <p class="muted small">가입할 때 입력한 이름, 학번, 비밀번호로 로그인합니다.</p>
      </div>
      <label class="field">이름
        <input v-model="name" type="text" autocomplete="name" required />
      </label>
      <label class="field">학번
        <input v-model="studentId" type="text" inputmode="numeric" autocomplete="username" required />
      </label>
      <label class="field">비밀번호
        <input v-model="password" type="password" autocomplete="current-password" required />
      </label>
      <p v-if="error" class="notice notice-error" role="alert">{{ error }}</p>
      <button class="btn btn-primary btn-block" type="submit" :disabled="busy">
        {{ busy ? '로그인 중…' : '로그인' }}
      </button>
      <p class="muted small">
        처음이신가요? <RouterLink to="/signup">회원가입</RouterLink> · 비밀번호를 잊었다면 임원진에게 초기화를 요청하세요.
      </p>
    </form>
  </div>
</template>
