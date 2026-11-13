import { supabase } from './supabase'

const API_BASE = (import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000').replace(/\/+$/, '')

export class ApiError extends Error {
  status: number
  code: string
  constructor(status: number, message: string, code = '') {
    super(message)
    this.status = status
    this.code = code
  }
}

type ApiOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  /** false 면 로그인 토큰 없이 호출 (로그인 요청 전용) */
  auth?: boolean
  query?: Record<string, string | number | null | undefined>
}

const toMessage = (detail: unknown, status: number): string => {
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail) && detail.length > 0) return '입력값을 다시 확인해주세요.'
  if (status === 401) return '로그인이 필요합니다.'
  if (status === 403) return '권한이 없습니다.'
  return '요청을 처리하지 못했습니다. 잠시 후 다시 시도해주세요.'
}

export async function api<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const { method = 'GET', body, auth = true, query } = options
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  if (auth) {
    const { data } = await supabase.auth.getSession()
    const token = data.session?.access_token
    if (!token) throw new ApiError(401, '로그인이 필요합니다.')
    headers.Authorization = `Bearer ${token}`
  }

  let url = `${API_BASE}${path}`
  if (query) {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(query)) {
      if (value !== null && value !== undefined && value !== '') params.set(key, String(value))
    }
    const qs = params.toString()
    if (qs) url += `?${qs}`
  }

  let response: Response
  try {
    response = await fetch(url, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, '서버에 연결하지 못했습니다. 인터넷 연결을 확인해주세요.')
  }

  let payload: unknown = null
  try {
    payload = await response.json()
  } catch {
    payload = null
  }

  if (!response.ok) {
    const detail = (payload as { detail?: unknown } | null)?.detail
    if (detail === 'PASSWORD_CHANGE_REQUIRED') {
      throw new ApiError(403, '초기화된 비밀번호를 먼저 변경해주세요.', 'PASSWORD_CHANGE_REQUIRED')
    }
    throw new ApiError(response.status, toMessage(detail, response.status))
  }
  return payload as T
}

export const errorMessage = (error: unknown): string =>
  error instanceof Error && error.message ? error.message : '알 수 없는 오류가 발생했습니다.'

/** 서버가 잠들어 있을 때(Cloud Run cold start) 미리 깨워 둡니다. 실패해도 무시합니다. */
export function warmUpBackend(): void {
  fetch(`${API_BASE}/health`, { cache: 'no-store' }).catch(() => undefined)
}
