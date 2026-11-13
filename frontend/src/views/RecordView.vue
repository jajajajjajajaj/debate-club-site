<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { api, errorMessage } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { todayKey } from '@/lib/time'
import { DEBATE_TYPES, type Debate, type MemberStatsRow, type Side } from '@/lib/types'

const { isAdmin } = useAuth()

const tab = ref<'list' | 'ranking'>('list')

// ---- 토론 목록 ----
const currentYear = Number(todayKey().slice(0, 4))
const years = Array.from({ length: Math.max(1, currentYear - 2019) }, (_, i) => currentYear - i)
const year = ref<number | ''>(currentYear)
const semester = ref<1 | 2 | ''>('')
const debateType = ref('')
const keyword = ref('')

const debates = ref<Debate[]>([])
const loading = ref(false)
const error = ref('')

let loadToken = 0
async function loadDebates() {
  const token = ++loadToken
  loading.value = true
  error.value = ''
  try {
    const data = await api<Debate[]>('/debates', {
      query: {
        year: year.value,
        semester: year.value === '' ? '' : semester.value,
        debate_type: debateType.value,
      },
    })
    if (token === loadToken) debates.value = data
  } catch (e) {
    if (token === loadToken) error.value = errorMessage(e)
  } finally {
    if (token === loadToken) loading.value = false
  }
}

watch([year, semester, debateType], loadDebates)

const filtered = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  if (!q) return debates.value
  return debates.value.filter(
    (d) => d.topic.toLowerCase().includes(q) || d.participants.some((p) => p.name.toLowerCase().includes(q)),
  )
})

const names = (d: Debate, side: Side): string =>
  d.participants
    .filter((p) => p.side === side)
    .map((p) => p.name)
    .join(', ') || '-'

// ---- 전적 순위 ----
const stats = ref<MemberStatsRow[]>([])
const statsLoaded = ref(false)
const statsError = ref('')

async function loadStats() {
  statsError.value = ''
  try {
    stats.value = await api<MemberStatsRow[]>('/members/stats')
    statsLoaded.value = true
  } catch (e) {
    statsError.value = errorMessage(e)
  }
}

watch(tab, (value) => {
  if (value === 'ranking' && !statsLoaded.value) void loadStats()
})

const ranked = computed(() => stats.value.filter((row) => row.total > 0))
const percent = (rate: number): string => `${Math.round(rate * 100)}%`

onMounted(loadDebates)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h1>토론 기록</h1>
      <RouterLink v-if="isAdmin" class="btn btn-primary" to="/record/manage">새 토론 기록</RouterLink>
    </div>

    <div class="tabs" role="tablist">
      <button class="tab" :class="{ active: tab === 'list' }" role="tab" :aria-selected="tab === 'list'" type="button" @click="tab = 'list'">토론 목록</button>
      <button class="tab" :class="{ active: tab === 'ranking' }" role="tab" :aria-selected="tab === 'ranking'" type="button" @click="tab = 'ranking'">전적 순위</button>
    </div>

    <template v-if="tab === 'list'">
      <div class="card filters">
        <label class="field">연도
          <select v-model="year">
            <option value="">전체</option>
            <option v-for="y in years" :key="y" :value="y">{{ y }}년</option>
          </select>
        </label>
        <label class="field">학기
          <select v-model="semester" :disabled="year === ''">
            <option value="">전체</option>
            <option :value="1">1학기 (3~8월)</option>
            <option :value="2">2학기 (9~2월)</option>
          </select>
        </label>
        <label class="field">방식
          <select v-model="debateType">
            <option value="">전체</option>
            <option v-for="t in DEBATE_TYPES" :key="t" :value="t">{{ t }}</option>
          </select>
        </label>
        <label class="field grow">검색
          <input v-model="keyword" type="text" placeholder="논제 또는 참가자 이름" />
        </label>
      </div>

      <p v-if="error" class="notice notice-error" role="alert">{{ error }}</p>
      <p v-else-if="loading" class="empty">불러오는 중…</p>
      <p v-else-if="filtered.length === 0" class="empty">조건에 맞는 토론 기록이 없습니다.</p>

      <ul v-else class="debate-list">
        <li v-for="d in filtered" :key="d.id" class="card">
          <div class="row">
            <span class="muted small">{{ d.debate_date }}</span>
            <span class="badge">{{ d.debate_type }}</span>
            <span v-if="d.winner_side === 'pro'" class="badge badge-pro">찬성 승</span>
            <span v-else-if="d.winner_side === 'con'" class="badge badge-con">반대 승</span>
            <span v-else class="badge">결과 미정</span>
            <RouterLink v-if="isAdmin" class="small" style="margin-left: auto" :to="{ name: 'debate-manage', query: { id: d.id } }">수정</RouterLink>
          </div>
          <h2 class="topic">{{ d.topic }}</h2>
          <div class="sides">
            <div :class="{ winner: d.winner_side === 'pro' }"><span class="badge badge-pro">찬성</span> {{ names(d, 'pro') }}</div>
            <div :class="{ winner: d.winner_side === 'con' }"><span class="badge badge-con">반대</span> {{ names(d, 'con') }}</div>
          </div>
          <p v-if="d.notes" class="muted small notes">{{ d.notes }}</p>
        </li>
      </ul>
    </template>

    <template v-else>
      <p v-if="statsError" class="notice notice-error" role="alert">{{ statsError }}</p>
      <p v-else-if="!statsLoaded" class="empty">불러오는 중…</p>
      <p v-else-if="ranked.length === 0" class="empty">아직 집계할 토론 기록이 없습니다.</p>
      <div v-else class="card table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th class="num">순위</th><th>이름</th><th>기수</th><th>학과</th>
              <th class="num">참가</th><th class="num">승</th><th class="num">패</th><th class="num">승률</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, i) in ranked" :key="row.user_id">
              <td class="num">{{ i + 1 }}</td>
              <td><strong>{{ row.name }}</strong></td>
              <td>{{ row.generation || '-' }}</td>
              <td>{{ row.major || '-' }}</td>
              <td class="num">{{ row.total }}</td>
              <td class="num">{{ row.wins }}</td>
              <td class="num">{{ row.losses }}</td>
              <td class="num">{{ row.wins + row.losses > 0 ? percent(row.win_rate) : '-' }}</td>
            </tr>
          </tbody>
        </table>
        <p class="muted small" style="margin-top: 10px">승패는 결과가 기록된 토론만 셉니다. 순위는 승수, 승률, 참가 횟수 순입니다.</p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.filters { display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-end; margin-bottom: 16px; }
.filters .field { min-width: 130px; }
.debate-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 12px; }
.topic { margin: 8px 0; font-size: 17px; }
.sides { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
@media (max-width: 640px) { .sides { grid-template-columns: 1fr; } }
.sides .winner { font-weight: 700; }
.notes { margin-top: 10px; white-space: pre-wrap; }
</style>
