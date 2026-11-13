<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'

type Team = 'pro' | 'con'
type Phase = {
  name: string
  /** single: 한 사람이 발언 / dual: 양 팀이 각자 시간을 나눠 쓰는 자유토론 */
  kind: 'single' | 'dual'
  /** single 은 전체 시간, dual 은 팀별 시간 (초) */
  seconds: number
  side: Team | 'none'
}

// 기본 순서와 시간은 예시입니다. 화면의 '순서 편집'에서 동아리 규칙에 맞게 고쳐 쓰세요.
const DEFAULT_PRESETS: Record<string, Phase[]> = {
  자유토론: [
    { name: '찬성 입론', kind: 'single', seconds: 180, side: 'pro' },
    { name: '반대 입론', kind: 'single', seconds: 180, side: 'con' },
    { name: '작전 시간', kind: 'single', seconds: 120, side: 'none' },
    { name: '자유토론', kind: 'dual', seconds: 420, side: 'none' },
    { name: '작전 시간', kind: 'single', seconds: 120, side: 'none' },
    { name: '반대 최종발언', kind: 'single', seconds: 120, side: 'con' },
    { name: '찬성 최종발언', kind: 'single', seconds: 120, side: 'pro' },
  ],
  SSU토론: [
    { name: '찬성 입론', kind: 'single', seconds: 240, side: 'pro' },
    { name: '반대 교차질의', kind: 'single', seconds: 180, side: 'con' },
    { name: '반대 입론', kind: 'single', seconds: 240, side: 'con' },
    { name: '찬성 교차질의', kind: 'single', seconds: 180, side: 'pro' },
    { name: '숙의 시간', kind: 'single', seconds: 120, side: 'none' },
    { name: '찬성 반론', kind: 'single', seconds: 180, side: 'pro' },
    { name: '반대 반론', kind: 'single', seconds: 180, side: 'con' },
    { name: '반대 최종발언', kind: 'single', seconds: 120, side: 'con' },
    { name: '찬성 최종발언', kind: 'single', seconds: 120, side: 'pro' },
  ],
}

const STORAGE_KEY = 'debate-timer-presets-v1'
const WARNING_MS = 30_000

const clonePhases = (phases: Phase[]): Phase[] => phases.map((p) => ({ ...p }))

function loadSaved(): Record<string, Phase[]> {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw) as Record<string, Phase[]>
    const result: Record<string, Phase[]> = {}
    for (const name of Object.keys(DEFAULT_PRESETS)) {
      const list = parsed?.[name]
      if (Array.isArray(list) && list.length > 0) {
        result[name] = list
          .filter((p) => p && typeof p.name === 'string' && Number.isFinite(p.seconds))
          .map((p): Phase => ({
            name: p.name,
            kind: p.kind === 'dual' ? 'dual' : 'single',
            seconds: Math.max(5, Math.round(p.seconds)),
            side: p.side === 'pro' || p.side === 'con' ? p.side : 'none',
          }))
      }
    }
    return result
  } catch {
    return {}
  }
}

const saved = loadSaved()
const presetNames = Object.keys(DEFAULT_PRESETS)
const presetName = ref(presetNames[0])
const phases = reactive<Phase[]>(clonePhases(saved[presetName.value] ?? DEFAULT_PRESETS[presetName.value]))

function persist() {
  try {
    const all = loadSaved()
    all[presetName.value] = clonePhases(phases)
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(all))
  } catch {
    // 저장소를 쓸 수 없는 환경이면 이번 접속 동안만 유지됩니다.
  }
}

// ---------------- 타이머 상태 ----------------
const index = ref(0)
const running = ref(false)
const remaining = ref(0) // single
const teamRemaining = reactive<Record<Team, number>>({ pro: 0, con: 0 }) // dual
const activeTeam = ref<Team>('pro')
const warned = reactive<Record<string, boolean>>({})
const editing = ref(false)

const phase = computed<Phase | undefined>(() => phases[index.value])
const isDual = computed(() => phase.value?.kind === 'dual')

function resetPhase() {
  running.value = false
  const current = phase.value
  if (!current) return
  remaining.value = current.seconds * 1000
  teamRemaining.pro = current.seconds * 1000
  teamRemaining.con = current.seconds * 1000
  activeTeam.value = 'pro'
  for (const key of Object.keys(warned)) delete warned[key]
}

function goTo(i: number) {
  if (i < 0 || i >= phases.length) return
  index.value = i
  resetPhase()
}

function resetAll() {
  index.value = 0
  resetPhase()
}

// ---------------- 종소리 (브라우저 내장 소리 합성) ----------------
let audio: AudioContext | null = null

function ensureAudio() {
  try {
    if (!audio) audio = new AudioContext()
    if (audio.state === 'suspended') void audio.resume()
  } catch {
    audio = null
  }
}

function bell(times: number) {
  if (!audio) return
  const ctx = audio
  for (let i = 0; i < times; i += 1) {
    const at = ctx.currentTime + i * 0.45
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = 'sine'
    osc.frequency.value = 1320
    gain.gain.setValueAtTime(0.0001, at)
    gain.gain.exponentialRampToValueAtTime(0.5, at + 0.02)
    gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.4)
    osc.connect(gain).connect(ctx.destination)
    osc.start(at)
    osc.stop(at + 0.42)
  }
}

// ---------------- 시간 흐름 ----------------
let lastTick = 0
let timerId: number | undefined

function consume(key: string, before: number, elapsed: number): number {
  const after = Math.max(0, before - elapsed)
  if (before > WARNING_MS && after <= WARNING_MS && !warned[key]) {
    warned[key] = true
    bell(1)
  }
  if (before > 0 && after === 0) bell(2)
  return after
}

function tick() {
  const now = Date.now()
  const elapsed = now - lastTick
  lastTick = now
  if (!running.value || !phase.value) return

  if (isDual.value) {
    const team = activeTeam.value
    teamRemaining[team] = consume(team, teamRemaining[team], elapsed)
    if (teamRemaining[team] === 0) {
      const other: Team = team === 'pro' ? 'con' : 'pro'
      if (teamRemaining[other] > 0) activeTeam.value = other
      else running.value = false
    }
  } else {
    remaining.value = consume('single', remaining.value, elapsed)
    if (remaining.value === 0) running.value = false
  }
}

function toggle() {
  if (!phase.value) return
  ensureAudio()
  if (!running.value) {
    const finished = isDual.value ? teamRemaining.pro === 0 && teamRemaining.con === 0 : remaining.value === 0
    if (finished) return
    lastTick = Date.now()
  }
  running.value = !running.value
}

function switchTeam(team: Team) {
  if (!isDual.value || teamRemaining[team] === 0) return
  ensureAudio()
  activeTeam.value = team
  if (!running.value) {
    lastTick = Date.now()
    running.value = true
  }
}

const format = (ms: number): string => {
  const total = Math.ceil(ms / 1000)
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}

const sideLabel = (side: Phase['side']): string => (side === 'pro' ? '찬성' : side === 'con' ? '반대' : '공통')

// ---------------- 순서 편집 ----------------
watch(presetName, (name) => {
  const all = loadSaved()
  phases.splice(0, phases.length, ...clonePhases(all[name] ?? DEFAULT_PRESETS[name]))
  resetAll()
})

function addPhase() {
  phases.push({ name: '새 순서', kind: 'single', seconds: 120, side: 'none' })
  persist()
}

function removePhase(i: number) {
  if (phases.length <= 1) return
  phases.splice(i, 1)
  persist()
  if (index.value >= phases.length) index.value = phases.length - 1
  resetPhase()
}

function movePhase(i: number, delta: number) {
  const j = i + delta
  if (j < 0 || j >= phases.length) return
  const [item] = phases.splice(i, 1)
  phases.splice(j, 0, item)
  persist()
  resetAll()
}

function setMinutes(p: Phase, value: string) {
  const minutes = Math.max(0, Math.min(99, Math.floor(Number(value) || 0)))
  p.seconds = Math.max(5, minutes * 60 + (p.seconds % 60))
  onEdited()
}

function setSeconds(p: Phase, value: string) {
  const seconds = Math.max(0, Math.min(59, Math.floor(Number(value) || 0)))
  p.seconds = Math.max(5, Math.floor(p.seconds / 60) * 60 + seconds)
  onEdited()
}

function onEdited() {
  persist()
  if (!running.value) resetPhase()
}

function restoreDefaults() {
  if (!window.confirm(`'${presetName.value}' 순서를 기본값으로 되돌릴까요?`)) return
  phases.splice(0, phases.length, ...clonePhases(DEFAULT_PRESETS[presetName.value]))
  persist()
  resetAll()
}

// ---------------- 단축키: 스페이스(시작/정지), ←/→(이전/다음) ----------------
function onKey(event: KeyboardEvent) {
  const target = event.target as HTMLElement | null
  if (target && ['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON'].includes(target.tagName)) return
  if (event.code === 'Space') {
    event.preventDefault()
    toggle()
  } else if (event.code === 'ArrowRight') {
    goTo(index.value + 1)
  } else if (event.code === 'ArrowLeft') {
    goTo(index.value - 1)
  }
}

onMounted(() => {
  resetPhase()
  lastTick = Date.now()
  timerId = window.setInterval(tick, 100)
  window.addEventListener('keydown', onKey)
})

onBeforeUnmount(() => {
  if (timerId !== undefined) window.clearInterval(timerId)
  window.removeEventListener('keydown', onKey)
  if (audio) void audio.close()
})
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>토론 타이머</h1>
        <p class="muted small">종료 30초 전에 종이 한 번, 시간이 끝나면 두 번 울립니다. 스페이스: 시작/정지, ←/→: 순서 이동</p>
      </div>
      <div class="row">
        <label class="field" style="min-width: 140px">토론 방식
          <select v-model="presetName" :disabled="running">
            <option v-for="name in presetNames" :key="name" :value="name">{{ name }}</option>
          </select>
        </label>
        <button class="btn" type="button" :disabled="running" @click="editing = !editing">
          {{ editing ? '편집 닫기' : '순서 편집' }}
        </button>
      </div>
    </div>

    <div class="layout">
      <section class="card display" :class="phase?.side">
        <p class="muted">{{ index + 1 }} / {{ phases.length }}</p>
        <h2 class="phase-name">{{ phase?.name }}</h2>

        <div v-if="isDual" class="dual">
          <button
            v-for="team in (['pro', 'con'] as const)"
            :key="team"
            type="button"
            class="team"
            :class="[team, { active: activeTeam === team && running, done: teamRemaining[team] === 0 }]"
            @click="switchTeam(team)"
          >
            <span class="team-label">{{ team === 'pro' ? '찬성' : '반대' }}</span>
            <span class="clock" :class="{ warning: teamRemaining[team] <= WARNING_MS }">{{ format(teamRemaining[team]) }}</span>
            <span class="small">{{ activeTeam === team && running ? '발언 중' : '눌러서 발언권 넘기기' }}</span>
          </button>
        </div>
        <div v-else class="clock big" :class="{ warning: remaining <= WARNING_MS, done: remaining === 0 }" aria-live="off">
          {{ format(remaining) }}
        </div>

        <div class="row controls">
          <button class="btn" type="button" :disabled="index === 0" @click="goTo(index - 1)">이전</button>
          <button class="btn btn-primary start" type="button" @click="toggle">{{ running ? '정지' : '시작' }}</button>
          <button class="btn" type="button" @click="resetPhase">다시</button>
          <button class="btn" type="button" :disabled="index >= phases.length - 1" @click="goTo(index + 1)">다음</button>
        </div>
      </section>

      <aside class="card">
        <div class="row" style="justify-content: space-between; margin-bottom: 8px">
          <h3 style="margin: 0">순서</h3>
          <button class="btn btn-sm" type="button" @click="resetAll">처음으로</button>
        </div>
        <ol class="phase-list">
          <li v-for="(p, i) in phases" :key="i">
            <button type="button" class="phase-item" :class="{ current: i === index }" @click="goTo(i)">
              <span class="badge" :class="{ 'badge-pro': p.side === 'pro', 'badge-con': p.side === 'con' }">{{ sideLabel(p.side) }}</span>
              <span class="grow">{{ p.name }}</span>
              <span class="muted small">{{ p.kind === 'dual' ? '팀별 ' : '' }}{{ format(p.seconds * 1000) }}</span>
            </button>
          </li>
        </ol>
      </aside>
    </div>

    <section v-if="editing" class="card" style="margin-top: 16px">
      <div class="row" style="justify-content: space-between; margin-bottom: 12px">
        <h2 style="margin: 0">'{{ presetName }}' 순서 편집</h2>
        <div class="row">
          <button class="btn btn-sm" type="button" @click="addPhase">순서 추가</button>
          <button class="btn btn-sm btn-danger" type="button" @click="restoreDefaults">기본값으로</button>
        </div>
      </div>
      <p class="muted small">바꾼 내용은 이 브라우저에 저장됩니다.</p>
      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr><th>이름</th><th>방식</th><th>발언 측</th><th>분</th><th>초</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="(p, i) in phases" :key="i">
              <td><input v-model="p.name" type="text" maxlength="30" aria-label="순서 이름" @change="onEdited" /></td>
              <td>
                <select v-model="p.kind" aria-label="방식" @change="onEdited">
                  <option value="single">한 명 발언</option>
                  <option value="dual">양 팀 시간 나눠 쓰기</option>
                </select>
              </td>
              <td>
                <select v-model="p.side" aria-label="발언 측" @change="onEdited">
                  <option value="pro">찬성</option>
                  <option value="con">반대</option>
                  <option value="none">공통</option>
                </select>
              </td>
              <td><input type="number" min="0" max="99" style="width: 72px" aria-label="분" :value="Math.floor(p.seconds / 60)" @change="setMinutes(p, ($event.target as HTMLInputElement).value)" /></td>
              <td><input type="number" min="0" max="59" style="width: 72px" aria-label="초" :value="p.seconds % 60" @change="setSeconds(p, ($event.target as HTMLInputElement).value)" /></td>
              <td>
                <div class="row" style="flex-wrap: nowrap">
                  <button class="btn btn-sm" type="button" aria-label="위로" :disabled="i === 0" @click="movePhase(i, -1)">↑</button>
                  <button class="btn btn-sm" type="button" aria-label="아래로" :disabled="i === phases.length - 1" @click="movePhase(i, 1)">↓</button>
                  <button class="btn btn-sm btn-danger" type="button" :disabled="phases.length <= 1" @click="removePhase(i)">삭제</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.layout { display: grid; grid-template-columns: 1fr 300px; gap: 16px; align-items: start; }
@media (max-width: 860px) { .layout { grid-template-columns: 1fr; } }
.display { text-align: center; padding: 32px 20px; border-top: 4px solid var(--border); }
.display.pro { border-top-color: var(--pro); }
.display.con { border-top-color: var(--con); }
.phase-name { font-size: 26px; margin-bottom: 8px; }
.clock { font-variant-numeric: tabular-nums; font-weight: 700; line-height: 1.1; }
.clock.big { font-size: clamp(72px, 18vw, 168px); }
.clock.warning { color: var(--warn); }
.clock.done, .team.done .clock { color: var(--danger); }
.controls { justify-content: center; margin-top: 20px; }
.start { min-width: 120px; font-size: 17px; padding: 12px 20px; }
.dual { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }
.team {
  font: inherit; cursor: pointer; border-radius: var(--radius); padding: 20px 8px; border: 2px solid var(--border);
  background: #fff; display: flex; flex-direction: column; align-items: center; gap: 6px; color: var(--text);
}
.team .clock { font-size: clamp(44px, 10vw, 96px); }
.team.pro .team-label { color: var(--pro); font-weight: 700; }
.team.con .team-label { color: var(--con); font-weight: 700; }
.team.pro.active { border-color: var(--pro); background: var(--pro-soft); }
.team.con.active { border-color: var(--con); background: var(--con-soft); }
.team.done { opacity: 0.6; cursor: not-allowed; }
.phase-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.phase-item {
  font: inherit; width: 100%; text-align: left; cursor: pointer; display: flex; align-items: center; gap: 8px;
  border: 1px solid transparent; border-radius: 8px; background: none; padding: 7px 8px; color: var(--text);
}
.phase-item:hover { background: #f1f3f6; }
.phase-item.current { background: var(--primary-soft); border-color: var(--primary); font-weight: 600; }
</style>
