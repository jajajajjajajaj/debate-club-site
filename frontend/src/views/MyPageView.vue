<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { errorMessage } from '@/lib/api'
import * as data from '@/lib/data'
import { useAuth } from '@/lib/auth'
import { SIDE_LABEL, type MyDebateItem } from '@/lib/types'

const { user } = useAuth()

const debates = ref<MyDebateItem[]>([])
const loading = ref(true)
const error = ref('')

const wins = computed(() => debates.value.filter((d) => d.result === 'win').length)
const losses = computed(() => debates.value.filter((d) => d.result === 'loss').length)
const winRate = computed(() => {
  const decided = wins.value + losses.value
  return decided > 0 ? `${Math.round((wins.value / decided) * 100)}%` : '-'
})

onMounted(async () => {
  try {
    debates.value = await data.listMyDebates()
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="page stack">
    <h1>마이페이지</h1>

    <section class="card">
      <div class="row" style="justify-content: space-between">
        <div>
          <h2 style="margin-bottom: 4px">{{ user?.name }} <span v-if="user?.role === 'admin'" class="badge badge-warn">관리자</span></h2>
          <p class="muted" style="margin: 0">
            {{ [user?.student_id, user?.major, user?.generation].filter(Boolean).join(' · ') }}
          </p>
        </div>
        <RouterLink class="btn" to="/change-password">비밀번호 변경</RouterLink>
      </div>
    </section>

    <div class="grid-3">
      <div class="card stat"><span class="muted small">참가</span><strong>{{ debates.length }}</strong></div>
      <div class="card stat"><span class="muted small">승 / 패</span><strong>{{ wins }} / {{ losses }}</strong></div>
      <div class="card stat"><span class="muted small">승률</span><strong>{{ winRate }}</strong></div>
    </div>

    <section class="card">
      <h2>내 토론</h2>
      <p v-if="error" class="notice notice-error" role="alert">{{ error }}</p>
      <p v-else-if="loading" class="muted">불러오는 중…</p>
      <p v-else-if="debates.length === 0" class="muted">아직 참가한 토론 기록이 없습니다.</p>
      <div v-else class="table-wrap">
        <table class="table">
          <thead><tr><th>날짜</th><th>논제</th><th>방식</th><th>내 입장</th><th>결과</th></tr></thead>
          <tbody>
            <tr v-for="d in debates" :key="d.debate_id">
              <td style="white-space: nowrap">{{ d.debate_date }}</td>
              <td>{{ d.topic }}</td>
              <td>{{ d.debate_type }}</td>
              <td><span class="badge" :class="d.side === 'pro' ? 'badge-pro' : 'badge-con'">{{ SIDE_LABEL[d.side] }}</span></td>
              <td>
                <span v-if="d.result === 'win'" class="badge badge-ok">승</span>
                <span v-else-if="d.result === 'loss'" class="badge">패</span>
                <span v-else class="muted small">미정</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.stat { display: flex; flex-direction: column; gap: 4px; }
.stat strong { font-size: 26px; font-variant-numeric: tabular-nums; }
</style>
