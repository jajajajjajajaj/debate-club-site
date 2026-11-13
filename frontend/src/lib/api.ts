// Supabase 응답 처리 도우미
type Result = { data: unknown; error: { message?: string } | null }

const HAS_KOREAN = /[가-힣]/

/** Supabase 오류를 사용자에게 보여줄 한국어 메시지로 바꿉니다. */
export function toKoreanError(message: string | undefined): string {
  const text = message ?? ''
  if (HAS_KOREAN.test(text)) return text // DB 함수가 직접 낸 안내 문구
  console.error('[supabase]', text)
  const lower = text.toLowerCase()
  if (lower.includes('failed to fetch') || lower.includes('network')) {
    return '서버에 연결하지 못했습니다. 인터넷 연결을 확인해주세요.'
  }
  if (lower.includes('jwt') || lower.includes('not authenticated')) return '로그인이 필요합니다. 다시 로그인해주세요.'
  if (lower.includes('permission denied') || lower.includes('row-level security')) return '권한이 없습니다.'
  return '요청을 처리하지 못했습니다. 잠시 후 다시 시도해주세요.'
}

/** 오류가 있으면 던지고, 없으면 data 를 돌려줍니다. */
export function unwrap<T>(result: Result): T {
  if (result.error) throw new Error(toKoreanError(result.error.message))
  return result.data as T
}

export const errorMessage = (error: unknown): string =>
  error instanceof Error && error.message ? error.message : '알 수 없는 오류가 발생했습니다.'
