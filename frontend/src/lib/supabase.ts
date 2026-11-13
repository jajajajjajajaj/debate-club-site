// Supabase 는 "로그인 상태(세션) 보관/갱신" 용도로만 씁니다.
// 데이터는 전부 백엔드 API 로 읽고 씁니다. (DB 는 브라우저 직접 접근이 막혀 있습니다)
import { createClient } from '@supabase/supabase-js'

const url = (import.meta.env.VITE_SUPABASE_URL ?? '').trim()
const anonKey = (import.meta.env.VITE_SUPABASE_ANON_KEY ?? '').trim()

export const isSupabaseConfigured = Boolean(url && anonKey)

if (!isSupabaseConfigured) {
  console.error('VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY 가 설정되지 않았습니다. frontend/.env 를 확인하세요.')
}

export const supabase = createClient(
  url || 'https://not-configured.supabase.co',
  anonKey || 'not-configured',
)
