<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { addDays, todayKey, weekdayOf } from '@/lib/time'

const props = defineProps<{
  /** 선택된 날짜 'YYYY-MM-DD' */
  modelValue: string
  /** 날짜별 예약 건수 */
  counts: Record<string, number>
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  /** 보고 있는 달이 바뀌면 그 달 1일의 날짜를 알려줍니다 */
  (e: 'month-change', firstDay: string): void
}>()

const firstOfMonth = (dateKey: string): string => `${dateKey.slice(0, 7)}-01`
const monthFirst = ref(firstOfMonth(props.modelValue))
const today = todayKey()

watch(
  () => props.modelValue,
  (value) => {
    if (firstOfMonth(value) !== monthFirst.value) monthFirst.value = firstOfMonth(value)
  },
)
watch(monthFirst, (value) => emit('month-change', value))

const title = computed(() => {
  const [y, m] = monthFirst.value.split('-').map(Number)
  return `${y}년 ${m}월`
})

const cells = computed(() => {
  const start = addDays(monthFirst.value, -weekdayOf(monthFirst.value))
  const month = monthFirst.value.slice(0, 7)
  return Array.from({ length: 42 }, (_, i) => {
    const key = addDays(start, i)
    return {
      key,
      day: Number(key.slice(8, 10)),
      inMonth: key.slice(0, 7) === month,
      weekday: i % 7,
      count: props.counts[key] ?? 0,
    }
  })
})

function moveMonth(delta: number) {
  const [y, m] = monthFirst.value.split('-').map(Number)
  const date = new Date(Date.UTC(y, m - 1 + delta, 1))
  monthFirst.value = `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}-01`
}

function goToday() {
  emit('update:modelValue', today)
  monthFirst.value = firstOfMonth(today)
}
</script>

<template>
  <div class="calendar">
    <div class="cal-head">
      <button class="btn btn-sm" type="button" aria-label="이전 달" @click="moveMonth(-1)">‹</button>
      <strong>{{ title }}</strong>
      <button class="btn btn-sm" type="button" aria-label="다음 달" @click="moveMonth(1)">›</button>
      <button class="btn btn-sm" type="button" style="margin-left: auto" @click="goToday">오늘</button>
    </div>
    <div class="cal-grid cal-week">
      <span v-for="(w, i) in ['일', '월', '화', '수', '목', '금', '토']" :key="w" :class="{ sun: i === 0, sat: i === 6 }">{{ w }}</span>
    </div>
    <div class="cal-grid">
      <button
        v-for="cell in cells"
        :key="cell.key"
        type="button"
        class="cal-cell"
        :class="{
          out: !cell.inMonth,
          selected: cell.key === modelValue,
          today: cell.key === today,
          sun: cell.weekday === 0,
          sat: cell.weekday === 6,
        }"
        :aria-pressed="cell.key === modelValue"
        :aria-label="`${cell.key}, 예약 ${cell.count}건`"
        @click="emit('update:modelValue', cell.key)"
      >
        <span>{{ cell.day }}</span>
        <span v-if="cell.count > 0" class="dot">{{ cell.count }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.cal-head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
.cal-week { font-size: 12px; color: var(--muted); text-align: center; margin-bottom: 4px; }
.cal-cell {
  font: inherit; background: none; border: 1px solid transparent; border-radius: 8px; cursor: pointer;
  min-height: 48px; padding: 4px; display: flex; flex-direction: column; align-items: center; gap: 2px; color: var(--text);
}
.cal-cell:hover { background: #f1f3f6; }
.cal-cell.out { opacity: 0.35; }
.cal-cell.today { border-color: var(--border); font-weight: 700; }
.cal-cell.selected { background: var(--primary-soft); border-color: var(--primary); }
.sun { color: var(--con); }
.sat { color: var(--pro); }
.dot { font-size: 11px; line-height: 1; padding: 2px 6px; border-radius: 999px; background: var(--primary); color: #fff; }
</style>
