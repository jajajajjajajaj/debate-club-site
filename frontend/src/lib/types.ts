export type Side = 'pro' | 'con'

export interface Profile {
  id: string
  email: string
  name: string
  student_id: string
  major: string
  generation: string
  role: 'member' | 'admin'
  must_change_password: boolean
}

export interface Participant {
  id: number
  user_id: string | null
  name: string
  side: Side
}

export interface Debate {
  id: string
  topic: string
  debate_date: string
  debate_type: string
  winner_side: Side | null
  notes: string
  participants: Participant[]
}

export interface ParticipantInput {
  user_id: string | null
  name: string
  side: Side
}

export interface DebateInput {
  topic: string
  debate_date: string
  debate_type: string
  winner_side: Side | null
  notes: string
  participants: ParticipantInput[]
}

export interface MyDebateItem {
  debate_id: string
  topic: string
  debate_date: string
  debate_type: string
  side: Side
  winner_side: Side | null
  result: 'win' | 'loss' | 'pending'
}

export interface MemberStatsRow {
  user_id: string
  name: string
  generation: string
  major: string
  wins: number
  losses: number
  total: number
  win_rate: number
}

export interface Reservation {
  id: string
  reserved_by: string
  reserved_by_name: string
  title: string
  starts_at: string
  ends_at: string
  debate_id: string | null
  allow_simultaneous: boolean
}

export const DEBATE_TYPES = ['자유토론', 'SSU토론'] as const
export const SIDE_LABEL: Record<Side, string> = { pro: '찬성', con: '반대' }
