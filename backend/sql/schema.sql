-- ============================================================
-- 토론 동아리 사이트 DB 스키마
-- 실행 위치: Supabase Dashboard > SQL Editor (한 번에 전체 실행)
--
-- 보안 원칙
--   * 모든 테이블에 RLS를 켜고 정책을 하나도 만들지 않습니다.
--     => 브라우저(anon / authenticated 키)에서는 어떤 테이블도 직접 읽고 쓸 수 없습니다.
--   * 데이터 접근은 전부 백엔드(FastAPI, service_role 키)를 거칩니다.
--     service_role 은 RLS를 우회하므로 백엔드에서만 권한 검사를 하면 됩니다.
-- ============================================================

begin;

create extension if not exists pgcrypto;

-- ------------------------------------------------------------
-- 공통: updated_at 자동 갱신
-- ------------------------------------------------------------
create or replace function public.touch_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ------------------------------------------------------------
-- 1) 회원 프로필 (auth.users 와 1:1)
-- ------------------------------------------------------------
create table if not exists public.users (
  id uuid primary key references auth.users (id) on delete cascade,
  email text not null unique,
  name text not null,
  student_id text not null unique,
  major text not null default '',
  generation text not null default '',
  role text not null default 'member' check (role in ('member', 'admin')),
  must_change_password boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists users_name_idx on public.users (name);

drop trigger if exists users_touch_updated_at on public.users;
create trigger users_touch_updated_at
before update on public.users
for each row execute function public.touch_updated_at();

-- ------------------------------------------------------------
-- 2) 토론
-- ------------------------------------------------------------
create table if not exists public.debates (
  id uuid primary key default gen_random_uuid(),
  topic text not null,
  debate_date date not null,
  debate_type text not null default '자유토론',
  winner_side text check (winner_side in ('pro', 'con')),
  notes text not null default '',
  created_by uuid references public.users (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists debates_date_idx on public.debates (debate_date desc);

drop trigger if exists debates_touch_updated_at on public.debates;
create trigger debates_touch_updated_at
before update on public.debates
for each row execute function public.touch_updated_at();

-- ------------------------------------------------------------
-- 3) 토론 참가자
--    user_id 가 없으면(졸업생·외부인 등) participant_name 만으로 기록합니다.
-- ------------------------------------------------------------
create table if not exists public.debate_participants (
  id bigint generated always as identity primary key,
  debate_id uuid not null references public.debates (id) on delete cascade,
  user_id uuid references public.users (id) on delete set null,
  participant_name text not null default '',
  side text not null check (side in ('pro', 'con')),
  created_at timestamptz not null default now()
);

create index if not exists debate_participants_debate_idx on public.debate_participants (debate_id);
create index if not exists debate_participants_user_idx on public.debate_participants (user_id);
create unique index if not exists debate_participants_unique_member
  on public.debate_participants (debate_id, user_id)
  where user_id is not null;

-- ------------------------------------------------------------
-- 4) 동아리방 예약 (방 1개)
--    시각은 실제 시각(timestamptz)으로 저장합니다. 한국 시간 변환은 화면에서 합니다.
-- ------------------------------------------------------------
create table if not exists public.reservations (
  id uuid primary key default gen_random_uuid(),
  reserved_by uuid not null references public.users (id) on delete cascade,
  reserved_by_name text not null default '',
  title text not null default '',
  starts_at timestamptz not null,
  ends_at timestamptz not null,
  debate_id uuid references public.debates (id) on delete set null,
  allow_simultaneous boolean not null default false,
  created_at timestamptz not null default now(),
  constraint reservations_time_order check (ends_at > starts_at)
);

create index if not exists reservations_starts_idx on public.reservations (starts_at);
create index if not exists reservations_ends_idx on public.reservations (ends_at);

-- ------------------------------------------------------------
-- 5) 예약 생성 함수 (겹침 검사 + 저장을 한 트랜잭션에서 처리)
--    같은 시간대에 동시에 요청이 들어와도 한도를 넘지 않도록 잠금을 겁니다.
--    규칙: 겹치는 예약은 최대 p_max_teams 팀, 그리고 겹치는 쪽 모두가 '동시 사용 허용'이어야 함.
-- ------------------------------------------------------------
create or replace function public.create_reservation(
  p_reserved_by uuid,
  p_reserved_by_name text,
  p_title text,
  p_starts_at timestamptz,
  p_ends_at timestamptz,
  p_debate_id uuid,
  p_allow_simultaneous boolean,
  p_max_teams integer default 2
)
returns public.reservations
language plpgsql
as $$
declare
  v_count integer;
  v_blocking integer;
  v_row public.reservations;
begin
  perform pg_advisory_xact_lock(hashtext('public.reservations'));

  select count(*), count(*) filter (where not allow_simultaneous)
    into v_count, v_blocking
  from public.reservations
  where starts_at < p_ends_at
    and ends_at > p_starts_at;

  if v_count >= p_max_teams then
    raise exception 'RESERVATION_FULL';
  end if;
  if v_count > 0 and v_blocking > 0 then
    raise exception 'RESERVATION_EXISTING_EXCLUSIVE';
  end if;
  if v_count > 0 and not p_allow_simultaneous then
    raise exception 'RESERVATION_NEEDS_SHARE';
  end if;

  insert into public.reservations (
    reserved_by, reserved_by_name, title, starts_at, ends_at, debate_id, allow_simultaneous
  )
  values (
    p_reserved_by, coalesce(p_reserved_by_name, ''), coalesce(p_title, ''),
    p_starts_at, p_ends_at, p_debate_id, coalesce(p_allow_simultaneous, false)
  )
  returning * into v_row;

  return v_row;
end;
$$;

revoke all on function public.create_reservation(uuid, text, text, timestamptz, timestamptz, uuid, boolean, integer)
  from public, anon, authenticated;
grant execute on function public.create_reservation(uuid, text, text, timestamptz, timestamptz, uuid, boolean, integer)
  to service_role;

-- ------------------------------------------------------------
-- 6) RLS: 전부 켜고 정책은 만들지 않음 (= 브라우저 직접 접근 전면 차단)
-- ------------------------------------------------------------
alter table public.users enable row level security;
alter table public.debates enable row level security;
alter table public.debate_participants enable row level security;
alter table public.reservations enable row level security;

revoke all on public.users, public.debates, public.debate_participants, public.reservations
  from anon, authenticated;

commit;
