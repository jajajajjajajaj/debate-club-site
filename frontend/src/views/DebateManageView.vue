<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { errorMessage } from '@/lib/api'
import * as data from '@/lib/data'
import { todayKey } from '@/lib/time'
import { DEBATE_TYPES, type DebateInput, type ParticipantInput, type Profile, type Side } from '@/lib/types'

const route = useRoute()
const router = useRouter()

const debateId = typeof route.query.id === 'string' ? route.query.id : ''
const isEdit = debateId !== ''

const form = reactive<DebateInput>({
  topic: '',
  debate_date: todayKey(),
  debate_type: DEBATE_TYPES[0],
  winner_side: null,
  notes: '',
  participants: [],
})

const members = ref<Profile[]>([])
const loading = ref(true)
const saving = ref(false)
const error = ref('')

// 찬성/반대 각각의 검색어
const search = reactive<Record<Side, string>>({ pro: '', con: '' })

const pickedIds = computed(() => new Set(form.participants.map((p) => p.user_id).filter((id): id is string => !!id)))

function candidates(side: Side): Profile[] {
  const q = search[side].trim().toLowerCase()
  if (!q) return []
  return members.value
    .filter((m) => !pickedIds.value.has(m.id) && (m.name.toLowerCase().includes(q) || m.student_id.includes(q)))
    .slice(0, 8)
}

function addMember(side: Side, member: Profile) {
  form.participants.push({ user_id: member.id, name: member.name, side })
  search[side] = ''
}

function addGuest(side: Side) {
  const name = search[side].trim()
  if (!name) return
  form.participants.push({ user_id: null, name, side })
  search[side] = ''
}

function removeParticipant(target: ParticipantInput) {
  const i = form.participants.indexOf(target)
  if (i >= 0) form.participants.splice(i, 1)
}

const bySide = (side: Side): ParticipantInput[] => form.participants.filter((p) => p.side === side)
const memberLabel = (m: Profile): string => [m.name, m.generation, m.major].filter(Boolean).join(' · ')

async function save() {
  if (saving.value) return
  error.value = ''
  if (!form.topic.trim()) {
    error.value = '논제를 입력해주세요.'
    return
  }
  saving.value = true
  try {
    const body: DebateInput = {
      ...form,
      topic: form.topic.trim(),
      participants: form.participants.map((p) => ({ ...p })),
    }
    await data.saveDebate(isEdit ? debateId : null, body)
    await router.push({ name: 'record' })
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

async function remove() {
  if (!isEdit || saving.value) return
  if (!window.confirm('이 토론 기록을 삭제할까요? 되돌릴 수 없습니다.')) return
  saving.value = true
  error.value = ''
  try {
    await data.deleteDebate(debateId)
    await router.push({ name: 'record' })
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    members.value = await data.listMembers()
    if (isEdit) {
      const debate = await data.getDebate(debateId)
      form.topic = debate.topic
      form.debate_date = debate.debate_date
      form.debate_type = debate.debate_type
      form.winner_side = debate.winner_side
      form.notes = debate.notes
      form.participants = debate.participants.map((p) => ({ user_id: p.user_id, name: p.name, side: p.side }))
    }
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h1>{{ isEdit ? '토론 기록 수정' : '새 토론 기록' }}</h1>
      <button class="btn" type="button" @click="router.push({ name: 'record' })">목록으로</button>
    </div>

    <p v-if="loading" class="empty">불러오는 중…</p>

    <form v-else class="stack" @submit.prevent="save">
      <section class="card stack">
        <label class="field">논제
          <input v-model="form.topic" type="text" maxlength="200" required />
        </label>
        <div class="grid-3">
          <label class="field">날짜
            <input v-model="form.debate_date" type="date" required />
          </label>
          <label class="field">방식
            <select v-model="form.debate_type">
              <option v-for="t in DEBATE_TYPES" :key="t" :value="t">{{ t }}</option>
              <option v-if="!(DEBATE_TYPES as readonly string[]).includes(form.debate_type)" :value="form.debate_type">{{ form.debate_type }}</option>
            </select>
          </label>
          <label class="field">결과
            <select v-model="form.winner_side">
              <option :value="null">미정</option>
              <option value="pro">찬성 승</option>
              <option value="con">반대 승</option>
            </select>
          </label>
        </div>
        <label class="field">메모 (선택)
          <textarea v-model="form.notes" maxlength="2000" />
        </label>
      </section>

      <div class="grid-2">
        <section v-for="side in (['pro', 'con'] as const)" :key="side" class="card stack">
          <h2 style="margin: 0">
            <span class="badge" :class="side === 'pro' ? 'badge-pro' : 'badge-con'">{{ side === 'pro' ? '찬성' : '반대' }}</span>
            참가자 {{ bySide(side).length }}명
          </h2>
          <ul class="chips">
            <li v-for="(p, i) in bySide(side)" :key="i">
              <span>{{ p.name }}</span>
              <span v-if="!p.user_id" class="badge">비회원</span>
              <button class="btn btn-sm" type="button" :aria-label="`${p.name} 빼기`" @click="removeParticipant(p)">×</button>
            </li>
            <li v-if="bySide(side).length === 0" class="muted">아직 없습니다.</li>
          </ul>
          <div class="row">
            <input v-model="search[side]" class="grow" type="text" placeholder="이름 또는 학번으로 회원 찾기" :aria-label="`${side === 'pro' ? '찬성' : '반대'} 참가자 검색`" @keydown.enter.prevent />
            <button class="btn btn-sm" type="button" :disabled="!search[side].trim()" @click="addGuest(side)">비회원으로 추가</button>
          </div>
          <ul v-if="candidates(side).length > 0" class="candidates">
            <li v-for="m in candidates(side)" :key="m.id">
              <button type="button" class="candidate" @click="addMember(side, m)">{{ memberLabel(m) }}</button>
            </li>
          </ul>
        </section>
      </div>

      <p v-if="error" class="notice notice-error" role="alert">{{ error }}</p>

      <div class="row">
        <button class="btn btn-primary" type="submit" :disabled="saving">{{ saving ? '저장 중…' : '저장' }}</button>
        <button v-if="isEdit" class="btn btn-danger" type="button" style="margin-left: auto" :disabled="saving" @click="remove">삭제</button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.chips { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 8px; }
.chips li { display: inline-flex; align-items: center; gap: 6px; }
.chips li:not(.muted) { border: 1px solid var(--border); border-radius: 999px; padding: 3px 4px 3px 12px; }
.candidates { list-style: none; margin: 0; padding: 4px; border: 1px solid var(--border); border-radius: 8px; }
.candidate { font: inherit; width: 100%; text-align: left; background: none; border: none; padding: 7px 8px; border-radius: 6px; cursor: pointer; color: var(--text); }
.candidate:hover { background: var(--primary-soft); }
</style>
