// 데이터 읽기/쓰기. 브라우저가 공개 키로 Supabase 에 직접 연결합니다.
// 읽기는 테이블 조회, 쓰기는 DB 함수(RPC) 호출입니다. 권한 검사는 DB 가 합니다.
import { unwrap } from './api'
import { supabase } from './supabase'
import { kstToIso } from './time'
import type {
  Debate,
  DebateInput,
  MemberStatsRow,
  MyDebateItem,
  Participant,
  Profile,
  Reservation,
  Side,
} from './types'

const asSide = (value: unknown): Side | null => (value === 'pro' || value === 'con' ? value : null)

// ---------------- 토론 ----------------
type ParticipantRow = { id: number; user_id: string | null; participant_name: string | null; side: Side }
type DebateRow = {
  id: string
  topic: string | null
  debate_date: string
  debate_type: string | null
  winner_side: string | null
  notes: string | null
  debate_participants: ParticipantRow[] | null
}

const DEBATE_SELECT =
  'id,topic,debate_date,debate_type,winner_side,notes,debate_participants(id,user_id,participant_name,side)'

const toDebate = (row: DebateRow): Debate => ({
  id: row.id,
  topic: row.topic ?? '',
  debate_date: row.debate_date,
  debate_type: row.debate_type || '자유토론',
  winner_side: asSide(row.winner_side),
  notes: row.notes ?? '',
  participants: (row.debate_participants ?? [])
    .slice()
    .sort((a, b) => a.id - b.id)
    .map((p): Participant => ({ id: p.id, user_id: p.user_id, name: p.participant_name ?? '', side: p.side })),
})

/** 1학기: 3~8월, 2학기: 9월~다음 해 2월. 학기를 고르지 않으면 그 해 1~12월. */
const semesterRange = (year: number, semester: 1 | 2 | null): [string, string] => {
  if (semester === 1) return [`${year}-03-01`, `${year}-09-01`]
  if (semester === 2) return [`${year}-09-01`, `${year + 1}-03-01`]
  return [`${year}-01-01`, `${year + 1}-01-01`]
}

export async function listDebates(filter: {
  year: number | null
  semester: 1 | 2 | null
  debateType: string
}): Promise<Debate[]> {
  let query = supabase.from('debates').select(DEBATE_SELECT)
  if (filter.year) {
    const [start, endExclusive] = semesterRange(filter.year, filter.semester)
    query = query.gte('debate_date', start).lt('debate_date', endExclusive)
  }
  if (filter.debateType) query = query.eq('debate_type', filter.debateType)
  const rows = unwrap<DebateRow[]>(await query.order('debate_date', { ascending: false }).order('id'))
  return rows.map(toDebate)
}

export async function getDebate(id: string): Promise<Debate> {
  const row = unwrap<DebateRow | null>(await supabase.from('debates').select(DEBATE_SELECT).eq('id', id).maybeSingle())
  if (!row) throw new Error('토론을 찾을 수 없습니다.')
  return toDebate(row)
}

/** id 가 null 이면 새로 만들고, 있으면 그 토론을 고칩니다. (관리자) */
export async function saveDebate(id: string | null, input: DebateInput): Promise<string> {
  return unwrap<string>(
    await supabase.rpc('save_debate', {
      p_id: id,
      p_topic: input.topic,
      p_debate_date: input.debate_date,
      p_debate_type: input.debate_type,
      p_winner_side: input.winner_side,
      p_notes: input.notes,
      p_participants: input.participants,
    }),
  )
}

export async function deleteDebate(id: string): Promise<void> {
  unwrap(await supabase.rpc('delete_debate', { p_id: id }))
}

// ---------------- 내 토론 / 전적 ----------------
async function currentUserId(): Promise<string> {
  const { data } = await supabase.auth.getSession()
  const id = data.session?.user?.id
  if (!id) throw new Error('로그인이 필요합니다.')
  return id
}

export async function listMyDebates(): Promise<MyDebateItem[]> {
  const userId = await currentUserId()
  type Row = {
    side: Side
    debates: { id: string; topic: string | null; debate_date: string; debate_type: string | null; winner_side: string | null } | null
  }
  const rows = unwrap<Row[]>(
    await supabase
      .from('debate_participants')
      .select('side,debates(id,topic,debate_date,debate_type,winner_side)')
      .eq('user_id', userId),
  )
  const items: MyDebateItem[] = []
  for (const row of rows) {
    const debate = row.debates
    if (!debate) continue
    const winner = asSide(debate.winner_side)
    items.push({
      debate_id: debate.id,
      topic: debate.topic ?? '',
      debate_date: debate.debate_date,
      debate_type: debate.debate_type || '자유토론',
      side: row.side,
      winner_side: winner,
      result: winner === null ? 'pending' : winner === row.side ? 'win' : 'loss',
    })
  }
  return items.sort((a, b) => (a.debate_date < b.debate_date ? 1 : a.debate_date > b.debate_date ? -1 : 0))
}

/** 회원별 통산 전적. 승패는 결과가 기록된 토론만 셉니다. */
export async function memberStats(): Promise<MemberStatsRow[]> {
  type UserRow = { id: string; name: string | null; generation: string | null; major: string | null }
  type StatDebate = { winner_side: string | null; debate_participants: { user_id: string | null; side: Side }[] | null }
  const [users, debates] = await Promise.all([
    supabase.from('users').select('id,name,generation,major'),
    supabase.from('debates').select('winner_side,debate_participants(user_id,side)'),
  ])

  const stats = new Map<string, MemberStatsRow>()
  for (const user of unwrap<UserRow[]>(users)) {
    stats.set(user.id, {
      user_id: user.id,
      name: (user.name ?? '').trim() || '이름 미입력',
      generation: (user.generation ?? '').trim(),
      major: (user.major ?? '').trim(),
      wins: 0,
      losses: 0,
      total: 0,
      win_rate: 0,
    })
  }
  for (const debate of unwrap<StatDebate[]>(debates)) {
    const winner = asSide(debate.winner_side)
    for (const part of debate.debate_participants ?? []) {
      const row = part.user_id ? stats.get(part.user_id) : undefined
      if (!row) continue
      row.total += 1
      if (winner === null) continue
      if (winner === part.side) row.wins += 1
      else row.losses += 1
    }
  }
  const result = [...stats.values()]
  for (const row of result) {
    const decided = row.wins + row.losses
    row.win_rate = decided > 0 ? row.wins / decided : 0
  }
  return result.sort(
    (a, b) => b.wins - a.wins || b.win_rate - a.win_rate || b.total - a.total || a.name.localeCompare(b.name, 'ko'),
  )
}

// ---------------- 예약 ----------------
const RESERVATION_SELECT = 'id,reserved_by,reserved_by_name,title,starts_at,ends_at,debate_id,allow_simultaneous'

/** startKey(포함) ~ endKey(제외) 사이의 한국 날짜에 걸친 예약 */
export async function listReservations(startKey: string, endKey: string): Promise<Reservation[]> {
  return unwrap<Reservation[]>(
    await supabase
      .from('reservations')
      .select(RESERVATION_SELECT)
      .lt('starts_at', kstToIso(endKey, 0))
      .gt('ends_at', kstToIso(startKey, 0))
      .order('starts_at')
      .order('id'),
  )
}

/** 같은 토론의 상대 팀이 겹치는 시간에 예약해 두었는지 */
async function opponentBooked(reservation: Reservation): Promise<boolean> {
  if (!reservation.debate_id) return false
  try {
    const [parts, overlapping] = await Promise.all([
      supabase.from('debate_participants').select('user_id,side').eq('debate_id', reservation.debate_id),
      supabase
        .from('reservations')
        .select('id,reserved_by')
        .eq('debate_id', reservation.debate_id)
        .lt('starts_at', reservation.ends_at)
        .gt('ends_at', reservation.starts_at),
    ])
    const sideByUser = new Map<string, Side>()
    for (const p of unwrap<{ user_id: string | null; side: Side }[]>(parts)) {
      if (p.user_id) sideByUser.set(p.user_id, p.side)
    }
    const mySide = sideByUser.get(reservation.reserved_by)
    if (!mySide) return false
    return unwrap<{ id: string; reserved_by: string }[]>(overlapping).some((r) => {
      const side = sideByUser.get(r.reserved_by)
      return r.id !== reservation.id && side !== undefined && side !== mySide
    })
  } catch {
    return false // 알림용 확인이라 실패해도 예약 자체에는 영향이 없습니다.
  }
}

export async function createReservation(input: {
  title: string
  starts_at: string
  ends_at: string
  debate_id: string | null
  allow_simultaneous: boolean
}): Promise<{ reservation: Reservation; warn_opponent_booked: boolean }> {
  const reservation = unwrap<Reservation>(
    await supabase.rpc('create_reservation', {
      p_title: input.title,
      p_starts_at: input.starts_at,
      p_ends_at: input.ends_at,
      p_debate_id: input.debate_id,
      p_allow_simultaneous: input.allow_simultaneous,
    }),
  )
  return { reservation, warn_opponent_booked: await opponentBooked(reservation) }
}

export async function cancelReservation(id: string): Promise<void> {
  const deleted = unwrap<{ id: string }[]>(await supabase.from('reservations').delete().eq('id', id).select('id'))
  if (deleted.length === 0) throw new Error('본인의 예약만 취소할 수 있습니다. (이미 취소된 예약일 수도 있습니다)')
}

// ---------------- 회원 관리 (관리자) ----------------
export async function listMembers(): Promise<Profile[]> {
  return unwrap<Profile[]>(await supabase.rpc('admin_list_members'))
}

export async function resetMemberPassword(userId: string): Promise<void> {
  unwrap(await supabase.rpc('admin_reset_password', { p_user: userId }))
}

export async function setMemberRole(userId: string, role: 'member' | 'admin'): Promise<void> {
  unwrap(await supabase.rpc('admin_set_role', { p_user: userId, p_role: role }))
}

export async function deleteMember(userId: string): Promise<void> {
  unwrap(await supabase.rpc('admin_delete_member', { p_user: userId }))
}
