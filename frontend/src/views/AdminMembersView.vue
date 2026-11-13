<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { errorMessage } from '@/lib/api'
import * as data from '@/lib/data'
import { useAuth } from '@/lib/auth'
import type { Profile } from '@/lib/types'

const { user } = useAuth()

const members = ref<Profile[]>([])
const loading = ref(true)
const error = ref('')
const notice = ref('')
const keyword = ref('')

async function loadMembers() {
  try {
    members.value = await data.listMembers()
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

const filtered = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  if (!q) return members.value
  return members.value.filter((m) => m.name.toLowerCase().includes(q) || m.student_id.includes(q))
})

// ---- 회원별 작업 ----
const busyId = ref('')

async function resetPassword(member: Profile) {
  if (!window.confirm(`${member.name} 님의 비밀번호를 학번으로 초기화할까요?`)) return
  busyId.value = member.id
  error.value = ''
  notice.value = ''
  try {
    await data.resetMemberPassword(member.id)
    notice.value = `${member.name} 님의 비밀번호를 학번으로 초기화했습니다. 다음 로그인 때 새 비밀번호를 정하게 됩니다.`
    await loadMembers()
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busyId.value = ''
  }
}

async function toggleRole(member: Profile) {
  const nextRole = member.role === 'admin' ? 'member' : 'admin'
  const question =
    nextRole === 'admin' ? `${member.name} 님을 관리자로 지정할까요?` : `${member.name} 님의 관리자 권한을 해제할까요?`
  if (!window.confirm(question)) return
  busyId.value = member.id
  error.value = ''
  notice.value = ''
  try {
    await data.setMemberRole(member.id, nextRole)
    await loadMembers()
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busyId.value = ''
  }
}

async function removeMember(member: Profile) {
  if (!window.confirm(`${member.name}(${member.student_id}) 님의 계정을 삭제할까요?\n예약은 함께 지워지고, 토론 기록의 이름은 남습니다. 되돌릴 수 없습니다.`)) return
  busyId.value = member.id
  error.value = ''
  notice.value = ''
  try {
    await data.deleteMember(member.id)
    notice.value = `${member.name} 님의 계정을 삭제했습니다.`
    await loadMembers()
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busyId.value = ''
  }
}

onMounted(loadMembers)
</script>

<template>
  <div class="page stack">
    <h1>회원 관리</h1>

    <p v-if="error" class="notice notice-error" role="alert">{{ error }}</p>
    <p v-if="notice" class="notice notice-ok" role="status">{{ notice }}</p>

    <section class="card stack">
      <div class="row" style="justify-content: space-between">
        <h2 style="margin: 0">회원 {{ members.length }}명</h2>
        <input v-model="keyword" type="text" placeholder="이름 또는 학번 검색" aria-label="회원 검색" style="max-width: 240px" />
      </div>
      <p v-if="loading" class="muted">불러오는 중…</p>
      <p v-else-if="filtered.length === 0" class="muted">회원이 없습니다.</p>
      <div v-else class="table-wrap">
        <table class="table">
          <thead>
            <tr><th>이름</th><th>학번</th><th>학과</th><th>기수</th><th>상태</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="m in filtered" :key="m.id">
              <td><strong>{{ m.name }}</strong> <span v-if="m.role === 'admin'" class="badge badge-warn">관리자</span></td>
              <td>{{ m.student_id }}</td>
              <td>{{ m.major || '-' }}</td>
              <td>{{ m.generation || '-' }}</td>
              <td>
                <span v-if="m.must_change_password" class="badge">비밀번호 초기화됨</span>
                <span v-else class="badge badge-ok">사용 중</span>
              </td>
              <td>
                <div class="row" style="flex-wrap: nowrap; justify-content: flex-end">
                  <button class="btn btn-sm" type="button" :disabled="busyId === m.id" @click="resetPassword(m)">비밀번호 초기화</button>
                  <button class="btn btn-sm" type="button" :disabled="busyId === m.id || m.id === user?.id" @click="toggleRole(m)">
                    {{ m.role === 'admin' ? '관리자 해제' : '관리자 지정' }}
                  </button>
                  <button class="btn btn-sm btn-danger" type="button" :disabled="busyId === m.id || m.id === user?.id" @click="removeMember(m)">삭제</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
