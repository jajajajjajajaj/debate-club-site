"""동아리방 예약 (방 1개, 30분 단위, 한국 시간 08:00~24:00)."""
from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app import config
from app.db import fetch_all, get_supabase
from app.schemas import ReservationCreateResponse, ReservationInput, ReservationOut, ReservationUpdate
from app.security import CurrentUser, get_current_user

router = APIRouter()

KST = timezone(timedelta(hours=9))
OPEN_HOUR = 8  # 08:00 부터
MAX_RANGE_DAYS = 100
COLUMNS = "id,reserved_by,reserved_by_name,title,starts_at,ends_at,debate_id,allow_simultaneous"


def _kst_midnight(day: date) -> datetime:
    return datetime.combine(day, time(0, 0), tzinfo=KST)


@router.get("", response_model=List[ReservationOut])
def list_reservations(
    start: date = Query(description="한국 날짜, 포함"),
    end: date = Query(description="한국 날짜, 제외"),
    _: CurrentUser = Depends(get_current_user),
):
    if end <= start:
        raise HTTPException(status_code=400, detail="end 는 start 보다 뒤여야 합니다.")
    if (end - start).days > MAX_RANGE_DAYS:
        raise HTTPException(status_code=400, detail=f"한 번에 최대 {MAX_RANGE_DAYS}일까지 조회할 수 있습니다.")

    range_start = _kst_midnight(start).isoformat()
    range_end = _kst_midnight(end).isoformat()
    sb = get_supabase()
    return fetch_all(
        lambda: sb.table("reservations")
        .select(COLUMNS)
        .lt("starts_at", range_end)
        .gt("ends_at", range_start)
        .order("starts_at")
        .order("id")
    )


def _validate_times(starts_at: datetime, ends_at: datetime) -> None:
    if starts_at.tzinfo is None or ends_at.tzinfo is None:
        raise HTTPException(status_code=400, detail="시각에는 시간대 정보가 있어야 합니다. (예: 2026-03-02T18:00:00+09:00)")
    start_kst = starts_at.astimezone(KST)
    end_kst = ends_at.astimezone(KST)
    if end_kst <= start_kst:
        raise HTTPException(status_code=400, detail="종료 시각은 시작 시각보다 뒤여야 합니다.")
    for moment in (start_kst, end_kst):
        if moment.minute not in (0, 30) or moment.second or moment.microsecond:
            raise HTTPException(status_code=400, detail="예약은 30분 단위로만 할 수 있습니다.")
    day_open = _kst_midnight(start_kst.date()) + timedelta(hours=OPEN_HOUR)
    day_close = _kst_midnight(start_kst.date()) + timedelta(days=1)
    if start_kst < day_open or end_kst > day_close:
        raise HTTPException(status_code=400, detail=f"예약 가능 시간은 {OPEN_HOUR:02d}:00~24:00 입니다.")
    if end_kst <= datetime.now(KST):
        raise HTTPException(status_code=400, detail="이미 지난 시간은 예약할 수 없습니다.")


def _check_debate_and_opponent(
    debate_id: str, owner_id: str, requester: CurrentUser, starts_at: datetime, ends_at: datetime
) -> bool:
    """토론 연습 예약일 때: 참가자인지 확인하고, 상대 팀이 같은 시간에 예약했는지 알려줍니다."""
    sb = get_supabase()
    debate = sb.table("debates").select("id").eq("id", debate_id).limit(1).execute()
    if not debate.data:
        raise HTTPException(status_code=400, detail="선택한 토론을 찾을 수 없습니다.")

    parts = fetch_all(
        lambda: sb.table("debate_participants")
        .select("user_id,side")
        .eq("debate_id", debate_id)
        .not_.is_("user_id", "null")
        .order("id")
    )
    side_by_user = {p["user_id"]: p["side"] for p in parts}
    my_side = side_by_user.get(owner_id)
    if my_side is None:
        if requester.is_admin:
            return False
        raise HTTPException(status_code=400, detail="해당 토론의 참가자만 그 토론으로 예약할 수 있습니다.")

    overlapping = (
        sb.table("reservations")
        .select("reserved_by")
        .eq("debate_id", debate_id)
        .lt("starts_at", ends_at.isoformat())
        .gt("ends_at", starts_at.isoformat())
        .execute()
    )
    return any(
        side_by_user.get(row["reserved_by"]) not in (None, my_side) for row in overlapping.data or []
    )


_RPC_ERRORS = {
    "RESERVATION_FULL": "이미 해당 시간대의 예약이 가득 찼습니다.",
    "RESERVATION_EXISTING_EXCLUSIVE": "해당 시간대의 기존 예약이 동시 사용을 허용하지 않습니다.",
    "RESERVATION_NEEDS_SHARE": "이미 예약이 있는 시간대입니다. '동시 사용 허용'을 켜야 함께 예약할 수 있습니다.",
}


@router.post("", response_model=ReservationCreateResponse)
def create_reservation(payload: ReservationInput, user: CurrentUser = Depends(get_current_user)):
    _validate_times(payload.starts_at, payload.ends_at)

    sb = get_supabase()
    owner_id, owner_name = user.id, user.name
    if payload.reserved_by and payload.reserved_by != user.id:
        if not user.is_admin:
            raise HTTPException(status_code=403, detail="본인 명의로만 예약할 수 있습니다.")
        owner = sb.table("users").select("id,name").eq("id", payload.reserved_by).limit(1).execute()
        if not owner.data:
            raise HTTPException(status_code=400, detail="대리 예약할 회원을 찾을 수 없습니다.")
        owner_id, owner_name = owner.data[0]["id"], owner.data[0].get("name") or ""

    warn_opponent = False
    if payload.debate_id:
        warn_opponent = _check_debate_and_opponent(
            payload.debate_id, owner_id, user, payload.starts_at, payload.ends_at
        )

    try:
        resp = sb.rpc(
            "create_reservation",
            {
                "p_reserved_by": owner_id,
                "p_reserved_by_name": owner_name,
                "p_title": payload.title.strip()[:100],
                "p_starts_at": payload.starts_at.isoformat(),
                "p_ends_at": payload.ends_at.isoformat(),
                "p_debate_id": payload.debate_id,
                "p_allow_simultaneous": payload.allow_simultaneous,
                "p_max_teams": config.max_concurrent_reservations(),
            },
        ).execute()
    except Exception as exc:
        text = str(getattr(exc, "message", "") or exc)
        for code, message in _RPC_ERRORS.items():
            if code in text:
                raise HTTPException(status_code=409, detail=message)
        raise HTTPException(status_code=500, detail="예약 저장에 실패했습니다. 잠시 후 다시 시도해주세요.")

    created = resp.data[0] if isinstance(resp.data, list) and resp.data else resp.data
    if not created:
        raise HTTPException(status_code=500, detail="예약 저장에 실패했습니다.")
    return {"reservation": created, "warn_opponent_booked": warn_opponent}


def _get_owned_reservation(reservation_id: str, user: CurrentUser, action: str) -> dict:
    resp = get_supabase().table("reservations").select(COLUMNS).eq("id", reservation_id).limit(1).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="예약을 찾을 수 없습니다.")
    row = resp.data[0]
    if row.get("reserved_by") != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail=f"본인의 예약만 {action}할 수 있습니다.")
    return row


@router.patch("/{reservation_id}", response_model=ReservationOut)
def update_reservation(
    reservation_id: str, payload: ReservationUpdate, user: CurrentUser = Depends(get_current_user)
):
    """예약 제목만 바꿀 수 있습니다. 시간을 바꾸려면 취소 후 다시 예약합니다."""
    _get_owned_reservation(reservation_id, user, "수정")
    sb = get_supabase()
    sb.table("reservations").update({"title": payload.title.strip()[:100]}).eq("id", reservation_id).execute()
    row = sb.table("reservations").select(COLUMNS).eq("id", reservation_id).limit(1).execute()
    if not row.data:
        raise HTTPException(status_code=404, detail="예약을 찾을 수 없습니다.")
    return row.data[0]


@router.delete("/{reservation_id}")
def cancel_reservation(reservation_id: str, user: CurrentUser = Depends(get_current_user)):
    _get_owned_reservation(reservation_id, user, "취소")
    get_supabase().table("reservations").delete().eq("id", reservation_id).execute()
    return {"ok": True, "id": reservation_id}
