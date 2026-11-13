-- ============================================================
-- 토론 동아리 사이트 DB (백엔드 서버 없이 Supabase만 쓰는 구조)
-- 실행 위치: Supabase Dashboard > SQL Editor (전체를 한 번에 실행)
-- 새 프로젝트에서도, 이전 버전 스키마를 이미 실행한 프로젝트에서도 그대로 실행하면 됩니다.
--
-- 보안 원칙
--   * 브라우저는 공개 키(publishable/anon)만 씁니다. Secret 키는 어디에도 필요 없습니다.
--   * 테이블은 로그인한 회원에게 '읽기'만 열어 두고, 쓰기는 전부 아래 함수(RPC)로만 합니다.
--     함수가 매번 로그인 여부·관리자 여부를 검사합니다.
--   * 회원이 자기 권한(role)을 직접 바꿀 방법은 없습니다.
-- ============================================================

begin;

create extension if not exists pgcrypto;

-- ------------------------------------------------------------
-- 테이블
-- ------------------------------------------------------------
create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.users (
  id uuid primary key references auth.users (id) on delete cascade,
  email text not null unique,
  name text not null,
  student_id text not null unique,
  major text not null default '',
  generation text not null default '',
  role text not null default 'member' check (role in ('member', 'admin')),
  must_change_password boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table public.users alter column must_change_password set default false;
create index if not exists users_name_idx on public.users (name);
drop trigger if exists users_touch_updated_at on public.users;
create trigger users_touch_updated_at before update on public.users
for each row execute function public.touch_updated_at();

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
create trigger debates_touch_updated_at before update on public.debates
for each row execute function public.touch_updated_at();

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
  on public.debate_participants (debate_id, user_id) where user_id is not null;

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

-- 이전 버전(백엔드 서버용) 함수 정리
drop function if exists public.create_reservation(uuid, text, text, timestamptz, timestamptz, uuid, boolean, integer);

-- ------------------------------------------------------------
-- 권한 확인 도우미
--   비밀번호가 초기화된 뒤 아직 바꾸지 않은 계정은 회원/관리자로 인정하지 않습니다.
-- ------------------------------------------------------------
create or replace function public.is_member()
returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.users where id = auth.uid() and not must_change_password);
$$;

create or replace function public.is_admin()
returns boolean language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from public.users
    where id = auth.uid() and role = 'admin' and not must_change_password
  );
$$;

-- ------------------------------------------------------------
-- 회원가입: 로그인 계정(auth.users)이 생기면 프로필을 자동으로 만듭니다.
--   권한은 항상 member 로 시작합니다. (가입 정보로 admin 이 될 수 없음)
-- ------------------------------------------------------------
create or replace function public.handle_new_auth_user()
returns trigger language plpgsql security definer set search_path = public as $$
declare
  v_sid text := btrim(coalesce(new.raw_user_meta_data ->> 'student_id', ''));
  v_name text := btrim(coalesce(new.raw_user_meta_data ->> 'name', ''));
begin
  if v_sid !~ '^[0-9]{8}$' then
    raise exception '학번은 숫자 8자리여야 합니다.';
  end if;
  if split_part(coalesce(new.email, ''), '@', 1) <> v_sid then
    raise exception '학번과 계정 정보가 일치하지 않습니다.';
  end if;
  if v_name = '' or char_length(v_name) > 30 then
    raise exception '이름을 30자 이내로 입력해주세요.';
  end if;

  insert into public.users (id, email, name, student_id, major, generation, role, must_change_password)
  values (
    new.id, new.email, v_name, v_sid,
    left(btrim(coalesce(new.raw_user_meta_data ->> 'major', '')), 50),
    left(btrim(coalesce(new.raw_user_meta_data ->> 'generation', '')), 20),
    'member', false
  );
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users
for each row execute function public.handle_new_auth_user();

-- ------------------------------------------------------------
-- 내 정보
-- ------------------------------------------------------------
create or replace function public.my_profile()
returns setof public.users language sql stable security definer set search_path = public as $$
  select * from public.users where id = auth.uid();
$$;

create or replace function public.mark_password_changed()
returns void language sql security definer set search_path = public as $$
  update public.users set must_change_password = false where id = auth.uid();
$$;

-- ------------------------------------------------------------
-- 관리자: 회원 관리
-- ------------------------------------------------------------
create or replace function public.admin_list_members()
returns setof public.users language plpgsql stable security definer set search_path = public as $$
begin
  if not public.is_admin() then
    raise exception '관리자 권한이 필요합니다.';
  end if;
  return query select * from public.users order by name, id;
end;
$$;

create or replace function public.admin_set_role(p_user uuid, p_role text)
returns void language plpgsql security definer set search_path = public as $$
begin
  if not public.is_admin() then
    raise exception '관리자 권한이 필요합니다.';
  end if;
  if p_role not in ('member', 'admin') then
    raise exception '올바르지 않은 권한입니다.';
  end if;
  if p_user = auth.uid() and p_role <> 'admin' then
    raise exception '본인의 관리자 권한은 직접 해제할 수 없습니다.';
  end if;
  update public.users set role = p_role where id = p_user;
  if not found then
    raise exception '회원을 찾을 수 없습니다.';
  end if;
end;
$$;

-- 비밀번호를 학번으로 초기화합니다. 그 회원은 다음 로그인 때 새 비밀번호를 정해야 합니다.
create or replace function public.admin_reset_password(p_user uuid)
returns void language plpgsql security definer set search_path = public, extensions as $$
declare
  v_sid text;
begin
  if not public.is_admin() then
    raise exception '관리자 권한이 필요합니다.';
  end if;
  select student_id into v_sid from public.users where id = p_user;
  if not found then
    raise exception '회원을 찾을 수 없습니다.';
  end if;
  update auth.users
    set encrypted_password = crypt(v_sid, gen_salt('bf')), updated_at = now()
    where id = p_user;
  update public.users set must_change_password = true where id = p_user;
end;
$$;

-- 계정 삭제: 그 회원의 예약은 함께 지워지고, 토론 기록의 이름은 남습니다.
create or replace function public.admin_delete_member(p_user uuid)
returns void language plpgsql security definer set search_path = public as $$
begin
  if not public.is_admin() then
    raise exception '관리자 권한이 필요합니다.';
  end if;
  if p_user = auth.uid() then
    raise exception '본인 계정은 삭제할 수 없습니다.';
  end if;
  delete from auth.users where id = p_user;
  if not found then
    raise exception '회원을 찾을 수 없습니다.';
  end if;
end;
$$;

-- ------------------------------------------------------------
-- 관리자: 토론 기록 저장/삭제 (토론과 참가자를 한 번에, 중간에 실패하면 전부 취소)
--   p_id 가 null 이면 새로 만들고, 있으면 그 토론을 고칩니다.
--   p_participants 예: [{"user_id": "…", "name": "", "side": "pro"}, {"user_id": null, "name": "외부인", "side": "con"}]
-- ------------------------------------------------------------
create or replace function public.save_debate(
  p_id uuid,
  p_topic text,
  p_debate_date date,
  p_debate_type text,
  p_winner_side text,
  p_notes text,
  p_participants jsonb
)
returns uuid language plpgsql security definer set search_path = public as $$
declare
  v_id uuid := p_id;
  v_item jsonb;
  v_uid uuid;
  v_name text;
  v_side text;
begin
  if not public.is_admin() then
    raise exception '관리자 권한이 필요합니다.';
  end if;
  if btrim(coalesce(p_topic, '')) = '' then
    raise exception '논제를 입력해주세요.';
  end if;
  if p_debate_date is null then
    raise exception '날짜를 입력해주세요.';
  end if;
  if p_winner_side is not null and p_winner_side not in ('pro', 'con') then
    raise exception '결과 값이 올바르지 않습니다.';
  end if;

  if v_id is null then
    insert into public.debates (topic, debate_date, debate_type, winner_side, notes, created_by)
    values (
      left(btrim(p_topic), 200), p_debate_date,
      coalesce(nullif(btrim(coalesce(p_debate_type, '')), ''), '자유토론'),
      p_winner_side, left(btrim(coalesce(p_notes, '')), 2000), auth.uid()
    )
    returning id into v_id;
  else
    update public.debates set
      topic = left(btrim(p_topic), 200),
      debate_date = p_debate_date,
      debate_type = coalesce(nullif(btrim(coalesce(p_debate_type, '')), ''), '자유토론'),
      winner_side = p_winner_side,
      notes = left(btrim(coalesce(p_notes, '')), 2000)
    where id = v_id;
    if not found then
      raise exception '토론을 찾을 수 없습니다.';
    end if;
    delete from public.debate_participants where debate_id = v_id;
  end if;

  for v_item in select value from jsonb_array_elements(coalesce(p_participants, '[]'::jsonb)) loop
    v_side := v_item ->> 'side';
    if v_side is null or v_side not in ('pro', 'con') then
      raise exception '참가자의 찬성/반대 값이 올바르지 않습니다.';
    end if;
    v_uid := nullif(v_item ->> 'user_id', '')::uuid;
    if v_uid is not null then
      select name into v_name from public.users where id = v_uid;
      if not found then
        raise exception '존재하지 않는 회원이 참가자에 포함되어 있습니다.';
      end if;
      if exists (select 1 from public.debate_participants where debate_id = v_id and user_id = v_uid) then
        raise exception '같은 회원이 두 번 들어가 있습니다.';
      end if;
    else
      v_name := left(btrim(coalesce(v_item ->> 'name', '')), 30);
      if v_name = '' then
        raise exception '참가자는 회원을 고르거나 이름을 입력해야 합니다.';
      end if;
    end if;
    insert into public.debate_participants (debate_id, user_id, participant_name, side)
    values (v_id, v_uid, v_name, v_side);
  end loop;

  return v_id;
end;
$$;

create or replace function public.delete_debate(p_id uuid)
returns void language plpgsql security definer set search_path = public as $$
begin
  if not public.is_admin() then
    raise exception '관리자 권한이 필요합니다.';
  end if;
  delete from public.debates where id = p_id;
  if not found then
    raise exception '토론을 찾을 수 없습니다.';
  end if;
end;
$$;

-- ------------------------------------------------------------
-- 예약 만들기 (규칙 검사 + 겹침 검사 + 저장을 한 번에)
--   한국 시간 08:00~24:00, 30분 단위, 지난 시간 불가.
--   같은 시간대에는 양쪽 모두 '동시 사용 허용'일 때만 최대 2팀.
-- ------------------------------------------------------------
create or replace function public.create_reservation(
  p_title text,
  p_starts_at timestamptz,
  p_ends_at timestamptz,
  p_debate_id uuid,
  p_allow_simultaneous boolean
)
returns public.reservations language plpgsql security definer set search_path = public as $$
declare
  v_start timestamp := p_starts_at at time zone 'Asia/Seoul';
  v_end timestamp := p_ends_at at time zone 'Asia/Seoul';
  v_name text;
  v_count integer;
  v_blocking integer;
  v_row public.reservations;
begin
  if not public.is_member() then
    raise exception '로그인이 필요합니다.';
  end if;
  if p_starts_at is null or p_ends_at is null or v_end <= v_start then
    raise exception '종료 시각은 시작 시각보다 뒤여야 합니다.';
  end if;
  if extract(minute from v_start) not in (0, 30) or extract(second from v_start) <> 0
     or extract(minute from v_end) not in (0, 30) or extract(second from v_end) <> 0 then
    raise exception '예약은 30분 단위로만 할 수 있습니다.';
  end if;
  if v_start < date_trunc('day', v_start) + interval '8 hours'
     or v_end > date_trunc('day', v_start) + interval '1 day' then
    raise exception '예약 가능 시간은 08:00~24:00 입니다.';
  end if;
  if p_ends_at <= now() then
    raise exception '이미 지난 시간은 예약할 수 없습니다.';
  end if;

  if p_debate_id is not null and not public.is_admin() and not exists (
    select 1 from public.debate_participants where debate_id = p_debate_id and user_id = auth.uid()
  ) then
    raise exception '해당 토론의 참가자만 그 토론으로 예약할 수 있습니다.';
  end if;

  -- 동시에 요청이 들어와도 한도를 넘지 않도록 잠급니다.
  perform pg_advisory_xact_lock(hashtext('public.reservations'));

  select count(*), count(*) filter (where not allow_simultaneous)
    into v_count, v_blocking
  from public.reservations
  where starts_at < p_ends_at and ends_at > p_starts_at;

  if v_count >= 2 then
    raise exception '이미 해당 시간대의 예약이 가득 찼습니다.';
  end if;
  if v_count > 0 and v_blocking > 0 then
    raise exception '해당 시간대의 기존 예약이 동시 사용을 허용하지 않습니다.';
  end if;
  if v_count > 0 and not coalesce(p_allow_simultaneous, false) then
    raise exception '이미 예약이 있는 시간대입니다. ''동시 사용 허용''을 켜야 함께 예약할 수 있습니다.';
  end if;

  select name into v_name from public.users where id = auth.uid();

  insert into public.reservations (
    reserved_by, reserved_by_name, title, starts_at, ends_at, debate_id, allow_simultaneous
  )
  values (
    auth.uid(), coalesce(v_name, ''), left(btrim(coalesce(p_title, '')), 100),
    p_starts_at, p_ends_at, p_debate_id, coalesce(p_allow_simultaneous, false)
  )
  returning * into v_row;

  return v_row;
end;
$$;

-- ------------------------------------------------------------
-- 접근 권한 (RLS)
-- ------------------------------------------------------------
alter table public.users enable row level security;
alter table public.debates enable row level security;
alter table public.debate_participants enable row level security;
alter table public.reservations enable row level security;

revoke all on public.users, public.debates, public.debate_participants, public.reservations
  from anon, authenticated;

-- 회원 목록: 다른 회원에게는 이름·학과·기수·권한만 보입니다. (학번·이메일은 본인과 관리자만, 함수로 조회)
grant select (id, name, major, generation, role) on public.users to authenticated;
drop policy if exists users_select on public.users;
create policy users_select on public.users for select to authenticated
  using (public.is_member());

grant select on public.debates, public.debate_participants, public.reservations to authenticated;

drop policy if exists debates_select on public.debates;
create policy debates_select on public.debates for select to authenticated
  using (public.is_member());

drop policy if exists debate_participants_select on public.debate_participants;
create policy debate_participants_select on public.debate_participants for select to authenticated
  using (public.is_member());

drop policy if exists reservations_select on public.reservations;
create policy reservations_select on public.reservations for select to authenticated
  using (public.is_member());

-- 예약 취소: 본인 예약이거나 관리자
grant delete on public.reservations to authenticated;
drop policy if exists reservations_delete on public.reservations;
create policy reservations_delete on public.reservations for delete to authenticated
  using (public.is_member() and (reserved_by = auth.uid() or public.is_admin()));

-- 함수 실행 권한: 로그인한 사용자만 (가입 트리거 함수는 아무도 직접 호출 불가)
revoke execute on function
  public.is_member(), public.is_admin(), public.my_profile(), public.mark_password_changed(),
  public.admin_list_members(), public.admin_set_role(uuid, text), public.admin_reset_password(uuid),
  public.admin_delete_member(uuid),
  public.save_debate(uuid, text, date, text, text, text, jsonb), public.delete_debate(uuid),
  public.create_reservation(text, timestamptz, timestamptz, uuid, boolean),
  public.handle_new_auth_user()
  from public, anon, authenticated;

grant execute on function
  public.is_member(), public.is_admin(), public.my_profile(), public.mark_password_changed(),
  public.admin_list_members(), public.admin_set_role(uuid, text), public.admin_reset_password(uuid),
  public.admin_delete_member(uuid),
  public.save_debate(uuid, text, date, text, text, text, jsonb), public.delete_debate(uuid),
  public.create_reservation(text, timestamptz, timestamptz, uuid, boolean)
  to authenticated;

commit;

-- API가 새 함수와 권한을 바로 인식하도록 합니다.
notify pgrst, 'reload schema';
