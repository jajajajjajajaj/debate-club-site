import { computed, reactive } from 'vue'
import { api } from './api'
import { supabase } from './supabase'
import type { Profile } from './types'

const state = reactive<{ user: Profile | null; ready: boolean }>({ user: null, ready: false })

let initPromise: Promise<void> | null = null

async function loadProfile(): Promise<void> {
  try {
    state.user = await api<Profile>('/members/me')
  } catch {
    state.user = null
  }
}

/** 앱 시작 시 한 번: 저장된 로그인 상태가 있으면 프로필을 불러옵니다. */
export function initAuth(): Promise<void> {
  if (!initPromise) {
    initPromise = (async () => {
      const { data } = await supabase.auth.getSession()
      if (data.session) await loadProfile()
      state.ready = true
    })()
  }
  return initPromise
}

supabase.auth.onAuthStateChange((event) => {
  // 이 콜백 안에서는 supabase 의 비동기 함수를 호출하지 않습니다(교착 방지).
  if (event === 'SIGNED_OUT') state.user = null
})

type LoginResponse = { access_token: string; refresh_token: string; must_change_password: boolean }

export async function login(name: string, studentId: string, password: string): Promise<Profile> {
  const tokens = await api<LoginResponse>('/auth/login', {
    method: 'POST',
    auth: false,
    body: { name: name.trim(), student_id: studentId.trim(), password },
  })
  const { error } = await supabase.auth.setSession({
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token,
  })
  if (error) throw new Error('로그인 상태를 저장하지 못했습니다. 다시 시도해주세요.')
  state.user = await api<Profile>('/members/me')
  state.ready = true
  return state.user
}

export type SignupInput = { name: string; studentId: string; password: string; major: string; generation: string }

export async function signup(input: SignupInput): Promise<Profile> {
  const tokens = await api<LoginResponse>('/auth/signup', {
    method: 'POST',
    auth: false,
    body: {
      name: input.name.trim(),
      student_id: input.studentId.trim(),
      password: input.password,
      major: input.major.trim(),
      generation: input.generation.trim(),
    },
  })
  const { error } = await supabase.auth.setSession({
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token,
  })
  if (error) throw new Error('가입은 되었지만 로그인 상태를 저장하지 못했습니다. 로그인 화면에서 로그인해주세요.')
  state.user = await api<Profile>('/members/me')
  state.ready = true
  return state.user
}

export async function changePassword(newPassword: string): Promise<void> {
  await api('/auth/change-password', { method: 'POST', body: { new_password: newPassword } })
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
