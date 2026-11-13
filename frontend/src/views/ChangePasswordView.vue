<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { errorMessage } from '@/lib/api'
import { changePassword, useAuth } from '@/lib/auth'

const router = useRouter()
const { mustChangePassword } = useAuth()
const forced = mustChangePassword.value

const password = ref('')
const confirm = ref('')
const busy = ref(false)
const error = ref('')

const mismatch = computed(() => confirm.value.length > 0 && password.value !== confirm.value)

async function onSubmit() {
  if (busy.value) return
  error.value = ''
  if (password.value.length < 8) {
    error.value = '비밀번호는 8자 이상이어야 합니다.'
    return
  }
  if (password.value !== confirm.value) {
    error.value = '두 비밀번호가 서로 다릅니다.'
    return
  }
  busy.value = true
  try {
    await changePassword(password.value)
    await router.replace(forced ? { name: 'home' } : { name: 'mypage' })
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
        <h1>비밀번호 변경</h1>
        <p v-if="forced" class="notice notice-warn">
          비밀번호가 학번으로 초기화된 상태입니다. 새 비밀번호를 정해야 다른 기능을 쓸 수 있습니다.
        </p>
      </div>
      <label class="field">새 비밀번호 (8자 이상, 학번 포함 불가)
        <input v-model="password" type="password" autocomplete="new-password" minlength="8" required />
      </label>
      <label class="field">새 비밀번호 확인
        <input v-model="confirm" type="password" autocomplete="new-password" required />
      </label>
      <p v-if="mismatch" class="small" style="color: var(--danger)">두 비밀번호가 서로 다릅니다.</p>
      <p v-if="error" class="notice notice-error" role="alert">{{ error }}</p>
      <button class="btn btn-primary btn-block" type="submit" :disabled="busy">
        {{ busy ? '변경 중…' : '비밀번호 변경' }}
      </button>
    </form>
  </div>
</template>
