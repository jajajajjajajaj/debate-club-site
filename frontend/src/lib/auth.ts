import { computed, reactive } from 'vue'
import { toKoreanError, unwrap } from './api'
import { supabase } from './supabase'
import type { Profile } from './types'

// Supabase 로그인은 이메일 기반이라, 학번으로 가상 이메일을 만들어 씁니다. (실제 메일은 가지 않습니다)
// 주의: 회원이 한 명이라도 가입한 뒤에는 이 도메인을 바꾸면 안 됩니다.
const EMAIL_DOMAIN = (import.meta.env.VITE_MEMBER_EMAIL_DOMAIN ?? '').trim() || 'member.debate-club.local'
const emailOf = (studentId: string): string => `${studentId}@${EMAIL_DOMAIN}`

const LOGIN_FAILED = '이름, 학번 또는 비밀번호가 올바르지 않습니다.'
const MIN_PASSWORD_LENGTH = 8

const state = reactive<{ user: Profile | null; ready: boolean }>({ user: null, ready: false })

let initPromise: Promise<void> | null = null

async function fetchProfile(): Promise<Profile | null> {
  return unwrap<Profile | null>(await supabase.rpc('my_profile').maybeSingle())
}

/** 앱 시작 시 한 번: 저장된 로그인 상태가 있으면 프로필을 불러옵니다. */
export function initAuth(): Promise<void> {
  if (!initPromise) {
    initPromise = (async () => {
      try {
        const { data } = await supabase.auth.getSession()
        state.user = data.session ? await fetchProfile() : null
      } catch {
        state.user = null
      }
      state.ready = true
    })()
  }
  return initPromise
}

supabase.auth.onAuthStateChange((event: string) => {
  // 이 콜백 안에서는 supabase 의 비동기 함수를 호출하지 않습니다(교착 방지).
  if (event === 'SIGNED_OUT') state.user = null
})

export function validatePassword(password: string, studentId: string): string | null {
  if (password.length < MIN_PASSWORD_LENGTH) return `비밀번호는 ${MIN_PASSWORD_LENGTH}자 이상이어야 합니다.`
  if (password !== password.trim()) return '비밀번호 앞뒤에 공백을 넣을 수 없습니다.'
  if (studentId && password.includes(studentId)) return '학번이 들어간 비밀번호는 사용할 수 없습니다.'
  return null
}

export async function login(name: string, studentId: string, password: string): Promise<Profile> {
  const cleanName = name.trim()
  const cleanId = studentId.trim()
  if (!cleanName || !cleanId || !password) throw new Error('이름, 학번, 비밀번호를 모두 입력해주세요.')

  const { error } = await supabase.auth.signInWithPassword({ email: emailOf(cleanId), password })
  if (error) {
    const text = (error.message ?? '').toLowerCase()
    if (text.includes('invalid login credentials')) throw new Error(LOGIN_FAILED)
    if (text.includes('rate limit') || text.includes('too many')) {
      throw new Error('로그인 시도가 너무 많습니다. 잠시 후 다시 시도해주세요.')
    }
    throw new Error(toKoreanError(error.message))
  }

  // 어느 항목이 틀렸는지는 알려주지 않습니다.
  const profile = await fetchProfile()
  if (!profile || profile.name.trim() !== cleanName) {
    await supabase.auth.signOut()
    throw new Error(LOGIN_FAILED)
  }
  state.user = profile
  state.ready = true
  return profile
}

export type SignupInput = { name: string; studentId: string; password: string; major: string; generation: string }

export async function signup(input: SignupInput): Promise<Profile> {
  const name = input.name.trim()
  const studentId = input.studentId.trim()
  if (!name || name.length > 30) throw new Error('이름을 30자 이내로 입력해주세요.')
  if (!/^\d{8}$/.test(studentId)) throw new Error('학번은 숫자 8자리여야 합니다.')
  const passwordProblem = validatePassword(input.password, studentId)
  if (passwordProblem) throw new Error(passwordProblem)

  const { data, error } = await supabase.auth.signUp({
    email: emailOf(studentId),
    password: input.password,
    options: {
      data: { name, student_id: studentId, major: input.major.trim(), generation: input.generation.trim() },
    },
  })
  if (error) {
    const text = (error.message ?? '').toLowerCase()
    if (text.includes('already registered') || text.includes('already been registered')) {
      throw new Error('이미 가입된 학번입니다. 로그인해주세요.')
    }
    if (text.includes('signups not allowed') || text.includes('signup is disabled')) {
      throw new Error('지금은 가입을 받을 수 없습니다. (Supabase 설정에서 새 사용자 가입 허용이 꺼져 있습니다)')
    }
    throw new Error(toKoreanError(error.message))
  }
  if (!data.session) {
    // Supabase 의 'Confirm email' 이 켜져 있으면 가입 직후 로그인되지 않습니다.
    throw new Error('가입을 완료하지 못했습니다. 이미 가입된 학번이거나, Supabase 설정에서 Confirm email 이 켜져 있습니다.')
  }

  const profile = await fetchProfile()
  if (!profile) throw new Error('가입은 되었지만 회원 정보를 불러오지 못했습니다. 로그인 화면에서 다시 로그인해주세요.')
  state.user = profile
  state.ready = true
  return profile
}

export async function changePassword(newPassword: string): Promise<void> {
  const problem = validatePassword(newPassword, state.user?.student_id ?? '')
  if (problem) throw new Error(problem)
  const { error } = await supabase.auth.updateUser({ password: newPassword })
  if (error) {
    const text = (error.message ?? '').toLowerCase()
    if (text.includes('different from the old')) throw new Error('지금 쓰는 비밀번호와 다른 비밀번호를 입력해주세요.')
    throw new Error(toKoreanError(error.message))
  }
  unwrap(await supabase.rpc('mark_password_changed'))
  if (state.user) state.user = { ...state.user, must_change_password: false }
}

export async function logout(): Promise<void> {
  await supabase.auth.signOut()
  state.user = null
}

export function useAuth() {
  return {
    user: computed(() => state.user),
    isReady: computed(() => state.ready),
    isLoggedIn: computed(() => state.user !== null),
    isAdmin: computed(() => state.user?.role === 'admin'),
    mustChangePassword: computed(() => state.user?.must_change_password === true),
  }
}
