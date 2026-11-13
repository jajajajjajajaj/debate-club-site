<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import MonthCalendar from '@/components/MonthCalendar.vue'
import { api, errorMessage } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { addDays, formatDateKey, kstDateKey, kstToIso, minutesToLabel, rangeWithinDay, todayKey } from '@/lib/time'
import type { MyDebateItem, Reservation } from '@/lib/types'

const OPEN_MIN = 8 * 60
const CLOSE_MIN = 24 * 60
const MAX_TEAMS = 2

const { user, isAdmin } = useAuth()

const selectedDate = ref(todayKey())
const monthFirst = ref(`${selectedDate.value.slice(0, 7)}-01`)
const reservations = ref<Reservation[]>([])
const loading = ref(false)
const loadError = ref('')

// ---- 조회: 보고 있는 달의 앞뒤 1주일까지 한 번에 가져옵니다 ----
let loadToken = 0
async function load() {
  const token = ++loadToken
  loading.value = true
  loadError.value = ''
  try {
    const [y, m] = monthFirst.value.split('-').map(Number)
    const next = new Date(Date.UTC(y, m, 1))
    const nextFirst = `${next.getUTCFullYear()}-${String(next.getUTCMonth() + 1).padStart(2, '0')}-01`
    const data = await api<Reservation[]>('/reservations', {
      query: { start: addDays(monthFirst.value, -7), end: addDays(nextFirst, 7) },
    })
    if (token === loadToken) reservations.value = data
  } catch (e) {
    if (token === loadToken) loadError.value = errorMessage(e)
  } finally {
    if (token === loadToken) loading.value = false
  }
}

watch(monthFirst, load)

const counts = computed(() => {
  const result: Record<string, number> = {}
  for (const r of reservations.value) {
    const key = kstDateKey(r.starts_at)
    result[key] = (result[key] ?? 0) + 1
  }
  return result
})

type DayItem = { reservation: Reservation; start: number; end: number }

const dayItems = computed<DayItem[]>(() => {
  const items: DayItem[] = []
  for (const r of reservations.value) {
    const range = rangeWithinDay(r.starts_at, r.ends_at, selectedDate.value)
    if (range) items.push({ reservation: r, start: range.start, end: range.end })
  }
  return items.sort((a, b) => a.start - b.start)
})

type Slot = { minute: number; items: DayItem[]; state: 'free' | 'shareable' | 'full' }

const slots = computed<Slot[]>(() => {
  const result: Slot[] = []
  for (let minute = OPEN_MIN; minute < CLOSE_MIN; minute += 30) {
    const items = dayItems.value.filter((i) => i.start < minute + 30 && i.end > minute)
    let state: Slot['state'] = 'free'
    if (items.length >= MAX_TEAMS || items.some((i) => !i.reservation.allow_simultaneous)) state = 'full'
    else if (items.length > 0) state = 'shareable'
    result.push({ minute, items, state })
  }
  return result
})

// ---- 예약 만들기 ----
const startMin = ref(18 * 60)
const endMin = ref(19 * 60)
const title = ref('')
const allowSimultaneous = ref(false)
const debateId = ref('')
const saving = ref(false)
const formError = ref('')
const formNotice = ref('')
const myDebates = ref<MyDebateItem[]>([])

const startOptions = computed(() => slots.value.map((s) => s.minute))
const endOptions = computed(() => {
  const options: number[] = []
  for (let minute = startMin.value + 30; minute <= CLOSE_MIN; minute += 30) options.push(minute)
  return options
})

watch(startMin, (value) => {
  if (endMin.value <= value) endMin.value = Math.min(value + 60, CLOSE_MIN)
})

const overlapping = computed(() => dayItems.value.filter((i) => i.start < endMin.value && i.end > startMin.value))
const needsShare = computed(() => overlapping.value.length > 0)
const isPast = computed(() => new Date(kstToIso(selectedDate.value, endMin.value)).getTime() <= Date.now())

function pickSlot(slot: Slot) {
  startMin.value = slot.minute
  endMin.value = Math.min(slot.minute + 60, CLOSE_MIN)
  formError.value = ''
  formNotice.value = ''
}

async function submit() {
  if (saving.value) return
  formError.value = ''
  formNotice.value = ''
  saving.value = true
  try {
    const result = await api<{ reservation: Reservation; warn_opponent_booked: boolean }>('/reservations', {
      method: 'POST',
      body: {
        title: title.value.trim(),
        starts_at: kstToIso(selectedDate.value, startMin.value),
        ends_at: kstToIso(selectedDate.value, endMin.value),
        debate_id: debateId.value || null,
        allow_simultaneous: allowSimultaneous.value,
      },
    })
    formNotice.value = result.warn_opponent_booked
      ? '예약했습니다. 참고: 같은 토론의 상대 팀도 이 시간에 예약해 두었습니다.'
      : '예약했습니다.'
    title.value = ''
    await load()
  } catch (e) {
    formError.value = errorMessage(e)
    await load()
  } finally {
    saving.value = false
  }
}

const canCancel = (r: Reservation): boolean => isAdmin.value || r.reserved_by === user.value?.id

async function cancel(r: Reservation) {
  if (!window.confirm('이 예약을 취소할까요?')) return
  formError.value = ''
  formNotice.value = ''
  try {
    await api(`/reservations/${encodeURIComponent(r.id)}`, { method: 'DELETE' })
    formNotice.value = '예약을 취소했습니다.'
  } catch (e) {
    formError.value = errorMessage(e)
  }
  await load()
}

onMounted(async () => {
  void load()
  try {
    const items = await api<MyDebateItem[]>('/members/me/debates')
    myDebates.value = items.filter((d) => d.result === 'pending')
  } catch {
    myDebates.value = []
  }
})
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>동아리방 예약</h1>
        <p class="muted small">08:00~24:00, 30분 단위. 같은 시간대에는 서로 '동시 사용 허용'일 때 최대 {{ MAX_TEAMS }}팀까지 예약됩니다.</p>
      </div>
    </div>

    <p v-if="loadError" class="notice notice-error" role="alert">{{ loadError }}</p>

    <div class="layout">
      <div class="stack">
        <section class="card">
          <MonthCalendar v-model="selectedDate" :counts="counts" @month-change="monthFirst = $event" />
        </section>

        <form class="card stack" @submit.prevent="submit">
          <h2>{{ formatDateKey(selectedDate) }} 예약하기</h2>
          <div class="grid-2">
            <label class="field">시작
              <select v-model.number="startMin">
                <option v-for="m in startOptions" :key="m" :value="m">{{ minutesToLabel(m) }}</option>
              </select>
            </label>
            <label class="field">종료
              <select v-model.number="endMin">
                <option v-for="m in endOptions" :key="m" :value="m">{{ minutesToLabel(m) }}</option>
              </select>
            </label>
          </div>
          <label class="field">사용 목적 (선택)
            <input v-model="title" type="text" maxlength="100" placeholder="예: 3주차 토론 준비" />
          </label>
          <label v-if="myDebates.length > 0" class="field">연결할 토론 (선택)
            <select v-model="debateId">
              <option value="">선택 안 함</option>
              <option v-for="d in myDebates" :key="d.debate_id" :value="d.debate_id">
                {{ d.debate_date }} · {{ d.topic }}
              </option>
            </select>
          </label>
          <label class="row">
            <input v-model="allowSimultaneous" type="checkbox" />
            <span>다른 팀과 동시 사용 허용</span>
          </label>
          <p v-if="needsShare" class="notice notice-warn">
            이 시간대에 이미 예약이 있습니다. 기존 예약과 내 예약 모두 '동시 사용 허용'이어야 예약됩니다.
          </p>
          <p v-if="formError" class="notice notice-error" role="alert">{{ formError }}</p>
          <p v-if="formNotice" class="notice notice-ok" role="status">{{ formNotice }}</p>
          <button class="btn btn-primary" type="submit" :disabled="saving || isPast">
            {{ isPast ? '지난 시간입니다' : saving ? '예약 중…' : `${minutesToLabel(startMin)}~${minutesToLabel(endMin)} 예약` }}
          </button>
        </form>
      </div>

      <section class="card">
        <h2>{{ formatDateKey(selectedDate) }} 시간표 <span v-if="loading" class="muted small">불러오는 중…</span></h2>
        <ul class="timeline">
          <li v-for="slot in slots" :key="slot.minute">
            <button
              type="button"
              class="slot"
              :class="[slot.state, { picked: slot.minute >= startMin && slot.minute < endMin }]"
              @click="pickSlot(slot)"
            >
              <span class="slot-time">{{ minutesToLabel(slot.minute) }}</span>
              <span class="slot-body">
                <template v-if="slot.items.length === 0">비어 있음</template>
                <span v-for="item in slot.items" :key="item.reservation.id" class="slot-item">
                  {{ item.reservation.reserved_by_name }}<template v-if="item.reservation.title"> · {{ item.reservation.title }}</template>
                </span>
              </span>
              <span v-if="slot.state === 'shareable'" class="badge badge-ok">함께 사용 가능</span>
              <span v-else-if="slot.state === 'full'" class="badge">마감</span>
            </button>
          </li>
        </ul>

        <h3 style="margin-top: 20px">이 날의 예약</h3>
        <p v-if="dayItems.length === 0" class="muted">예약이 없습니다.</p>
        <ul v-else class="day-list">
          <li v-for="item in dayItems" :key="item.reservation.id" class="row">
            <span class="badge badge-primary">{{ minutesToLabel(item.start) }}~{{ minutesToLabel(item.end) }}</span>
            <strong>{{ item.reservation.reserved_by_name }}</strong>
            <span class="muted grow">{{ item.reservation.title }}</span>
            <span v-if="item.reservation.allow_simultaneous" class="badge badge-ok">동시 사용 허용</span>
            <button v-if="canCancel(item.reservation)" class="btn btn-sm btn-danger" type="button" @click="cancel(item.reservation)">
              취소
            </button>
          </li>
        </ul>
      </section>
    </div>
  </div>
</template>

<style scoped>
.layout { display: grid; grid-template-columns: minmax(300px, 380px) 1fr; gap: 16px; align-items: start; }
@media (max-width: 860px) { .layout { grid-template-columns: 1fr; } }
.timeline { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 3px; }
.slot {
  font: inherit; width: 100%; text-align: left; cursor: pointer; display: flex; align-items: center; gap: 10px;
  border: 1px solid var(--border); border-radius: 8px; background: #fff; padding: 6px 10px; color: var(--text);
}
.slot:hover { border-color: var(--primary); }
.slot.shareable { background: var(--ok-soft); }
.slot.full { background: #f1f3f6; }
.slot.picked { border-color: var(--primary); box-shadow: inset 3px 0 0 var(--primary); }
.slot-time { font-variant-numeric: tabular-nums; color: var(--muted); width: 44px; flex: none; }
.slot-body { flex: 1 1 0; min-width: 0; display: flex; gap: 10px; flex-wrap: wrap; font-size: 14px; }
.slot.free .slot-body { color: var(--muted); }
.slot-item { font-weight: 600; }
.day-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
</style>
