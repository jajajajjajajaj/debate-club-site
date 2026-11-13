<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { addDays, formatDateKey, minutesToLabel, rangeWithinDay, todayKey } from '@/lib/time'
import type { Reservation } from '@/lib/types'

const clubName = import.meta.env.VITE_CLUB_NAME || '토론 동아리'
const { user, isLoggedIn, isAdmin } = useAuth()

const today = todayKey()
const todayReservations = ref<Reservation[]>([])
const loaded = ref(false)

const timeRange = (r: Reservation): string => {
  const range = rangeWithinDay(r.starts_at, r.ends_at, today)
  return range ? `${minutesToLabel(range.start)}~${minutesToLabel(range.end)}` : ''
}

onMounted(async () => {
  if (!isLoggedIn.value) return
  try {
    todayReservations.value = await api<Reservation[]>('/reservations', {
      query: { start: today, end: addDays(today, 1) },
    })
  } catch {
    todayReservations.value = []
  } finally {
    loaded.value = true
  }
})
</script>

<template>
  <div class="page stack">
    <div>
      <h1>{{ clubName }}</h1>
      <p v-if="isLoggedIn" class="muted">{{ user?.name }}님, 안녕하세요.</p>
      <template v-else>
        <p class="muted">동아리방 예약과 토론 기록은 로그인 후 이용할 수 있습니다. 처음이라면 회원가입을, 이미 가입했다면 로그인을 선택하세요.</p>
        <div class="row" style="margin-top: 12px">
          <RouterLink class="btn btn-primary" to="/signup">회원가입</RouterLink>
          <RouterLink class="btn" to="/login">로그인</RouterLink>
        </div>
      </template>
    </div>

    <div class="grid-3">
      <RouterLink class="card tile" to="/reservation">
        <h2>동아리방 예약</h2>
        <p class="muted small">30분 단위로 예약하고, 달력에서 한눈에 확인합니다.</p>
      </RouterLink>
      <RouterLink class="card tile" to="/timer">
        <h2>토론 타이머</h2>
        <p class="muted small">순서별 발언 시간을 재고 종료 전에 종을 울립니다.</p>
      </RouterLink>
      <RouterLink class="card tile" to="/record">
        <h2>토론 기록</h2>
        <p class="muted small">지난 토론의 논제·참가자·승패와 전적 순위를 봅니다.</p>
      </RouterLink>
    </div>

    <section v-if="isLoggedIn" class="card">
      <h2>오늘의 동아리방 · {{ formatDateKey(today) }}</h2>
      <p v-if="!loaded" class="muted">불러오는 중…</p>
      <p v-else-if="todayReservations.length === 0" class="muted">오늘은 예약이 없습니다.</p>
      <ul v-else class="today-list">
        <li v-for="r in todayReservations" :key="r.id">
          <span class="badge badge-primary">{{ timeRange(r) }}</span>
          <strong>{{ r.reserved_by_name }}</strong>
          <span class="muted">{{ r.title }}</span>
        </li>
      </ul>
    </section>

    <section v-if="isAdmin" class="card row">
      <span class="badge badge-warn">관리자</span>
      <RouterLink to="/admin/members">회원 관리</RouterLink>
      <RouterLink to="/record/manage">토론 기록 관리</RouterLink>
    </section>
  </div>
</template>

<style scoped>
.tile { color: var(--text); display: block; }
.tile:hover { border-color: var(--primary); }
.today-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.today-list li { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
</style>
