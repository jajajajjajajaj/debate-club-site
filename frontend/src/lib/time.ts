// 모든 화면 표시는 한국 시간(KST, UTC+9, 서머타임 없음) 기준입니다.
// 서버에는 실제 시각(ISO 8601, UTC)으로 주고받습니다.

const KST_OFFSET_MINUTES = 9 * 60
const pad = (n: number): string => String(n).padStart(2, '0')

/** Date 를 9시간 민 뒤 UTC 값으로 읽으면 한국 시간의 연/월/일/시/분이 됩니다. */
const shiftToKst = (value: Date | string): Date => {
  const date = typeof value === 'string' ? new Date(value) : value
  return new Date(date.getTime() + KST_OFFSET_MINUTES * 60_000)
}

/** 'YYYY-MM-DD' (한국 날짜) */
export const kstDateKey = (value: Date | string): string => {
  const k = shiftToKst(value)
  return `${k.getUTCFullYear()}-${pad(k.getUTCMonth() + 1)}-${pad(k.getUTCDate())}`
}

export const todayKey = (): string => kstDateKey(new Date())

/** 한국 시간 기준 자정부터 몇 분인지 */
export const kstMinutesOfDay = (value: Date | string): number => {
  const k = shiftToKst(value)
  return k.getUTCHours() * 60 + k.getUTCMinutes()
}

export const minutesToLabel = (minutes: number): string => `${pad(Math.floor(minutes / 60))}:${pad(minutes % 60)}`

/** 한국 날짜 + 자정부터의 분 -> ISO 문자열(UTC) */
export const kstToIso = (dateKey: string, minutesOfDay: number): string => {
  const [y, m, d] = dateKey.split('-').map(Number)
  const utcMs = Date.UTC(y, m - 1, d, 0, 0, 0) + (minutesOfDay - KST_OFFSET_MINUTES) * 60_000
  return new Date(utcMs).toISOString()
}

export const addDays = (dateKey: string, days: number): string => {
  const [y, m, d] = dateKey.split('-').map(Number)
  const date = new Date(Date.UTC(y, m - 1, d + days))
  return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}`
}

/** 0(일) ~ 6(토) */
export const weekdayOf = (dateKey: string): number => {
  const [y, m, d] = dateKey.split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d)).getUTCDay()
}

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토']

/** '3월 2일 (월)' */
export const formatDateKey = (dateKey: string): string => {
  const [, m, d] = dateKey.split('-').map(Number)
  return `${m}월 ${d}일 (${WEEKDAYS[weekdayOf(dateKey)]})`
}

/**
 * 예약 한 건이 주어진 한국 날짜 안에서 차지하는 구간(분).
 * 자정에 끝나는 예약은 끝을 1440(=24:00)으로 표시합니다.
 */
export const rangeWithinDay = (
  startsAt: string,
  endsAt: string,
  dateKey: string,
): { start: number; end: number } | null => {
  const dayStart = new Date(kstToIso(dateKey, 0)).getTime()
  const dayEnd = dayStart + 24 * 60 * 60_000
  const s = Math.max(new Date(startsAt).getTime(), dayStart)
  const e = Math.min(new Date(endsAt).getTime(), dayEnd)
  if (e <= s) return null
  return { start: Math.round((s - dayStart) / 60_000), end: Math.round((e - dayStart) / 60_000) }
}
