<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { errorMessage } from '@/lib/api'
import { signup } from '@/lib/auth'

const router = useRouter()

const form = reactive({ name: '', studentId: '', major: '', generation: '', password: '' })
const confirm = ref('')
const busy = ref(false)
const error = ref('')

const mismatch = computed(() => confirm.value.length > 0 && form.password !== confirm.value)

async function onSubmit() {
  if (busy.value) return
  error.value = ''
  if (!/^\d{8}$/.test(form.studentId.trim())) {
    error.value = '학번은 숫자 8자리여야 합니다.'
    return
  }
  if (form.password.length < 8) {
    error.value = '비밀번호는 8자 이상이어야 합니다.'
    return
  }
  if (form.password !== confirm.value) {
    error.value = '두 비밀번호가 서로 다릅니다.'
    return
  }
  busy.value = true
  try {
    await signup(form)
    await router.replace({ name: 'home' })
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
        <h1>회원가입</h1>
        <p class="muted small">가입하면 바로 로그인됩니다. 다음부터는 이름, 학번, 비밀번호로 로그인하세요.</p>
      </div>
      <label class="field">이름
        <input v-model="form.name" type="text" autocomplete="name" maxlength="30" required />
      </label>
      <label class="field">학번 (숫자 8자리)
        <input v-model="form.studentId" type="text" inputmode="numeric" autocomplete="username" maxlength="8" required />
      </label>
      <div class="grid-2">
        <label class="field">학과 (선택)
          <input v-model="form.major" type="text" maxlength="50" />
        </label>
        <label class="field">기수 (선택)
          <input v-model="form.generation" type="text" maxlength="20" />
        </label>
      </div>
      <label class="field">비밀번호 (8자 이상, 학번 포함 불가)
        <input v-model="form.password" type="password" autocomplete="new-password" minlength="8" required />
      </label>
      <label class="field">비밀번호 확인
        <input v-model="confirm" type="password" autocomplete="new-password" required />
      </label>
      <p v-if="mismatch" class="small" style="color: var(--danger)">두 비밀번호가 서로 다릅니다.</p>
      <p v-if="error" class="notice notice-error" role="alert">{{ error }}</p>
      <button class="btn btn-primary btn-block" type="submit" :disabled="busy">
        {{ busy ? '가입 중…' : '가입하기' }}
      </button>
      <p class="muted small">이미 가입했나요? <RouterLink to="/login">로그인</RouterLink></p>
    </form>
  </div>
</template>
