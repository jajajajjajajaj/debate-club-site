"""회원: 내 정보, 전적, 회원 관리(관리자)."""
import re
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException

from app import config
from app.db import fetch_all, get_supabase
from app.schemas import (
    MemberProfile,
    MemberStatsRow,
    MyDebateItem,
    RoleUpdateRequest,
)
from app.security import (
    CurrentUser,
    get_admin_user,
    get_current_user,
    get_pending_or_active_user,
)

router = APIRouter()

PROFILE_COLUMNS = "id,email,name,student_id,major,generation,role,must_change_password"
STUDENT_ID_PATTERN = re.compile(r"^\d{8}$")


def member_email(student_id: str) -> str:
    return f"{student_id}@{config.member_email_domain()}"


# ------------------------------------------------------------
# 내 정보
# ------------------------------------------------------------
@router.get("/me", response_model=MemberProfile)
def get_my_profile(user: CurrentUser = Depends(get_pending_or_active_user)):
    resp = get_supabase().table("users").select(PROFILE_COLUMNS).eq("id", user.id).limit(1).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="회원 정보를 찾을 수 없습니다.")
    return resp.data[0]


@router.get("/me/debates", response_model=List[MyDebateItem])
def list_my_debates(user: CurrentUser = Depends(get_current_user)):
    sb = get_supabase()
    parts = fetch_all(
        lambda: sb.table("debate_participants").select("debate_id,side").eq("user_id", user.id).order("id")
    )
    if not parts:
        return []
    side_by_debate = {p["debate_id"]: p["side"] for p in parts}

    debates: List[dict] = []
    ids = list(side_by_debate.keys())
    for start in range(0, len(ids), 100):
        resp = (
            sb.table("debates")
            .select("id,topic,debate_date,debate_type,winner_side")
            .in_("id", ids[start : start + 100])
            .execute()
        )
        debates.extend(resp.data or [])
    debates.sort(key=lambda d: d["debate_date"], reverse=True)

    items: List[MyDebateItem] = []
    for debate in debates:
        side = side_by_debate[debate["id"]]
        winner = debate.get("winner_side")
        if winner not in ("pro", "con"):
            result = "pending"
        else:
            result = "win" if winner == side else "loss"
        items.append(
            MyDebateItem(
                debate_id=debate["id"],
                topic=debate.get("topic") or "",
                debate_date=debate["debate_date"],
                debate_type=debate.get("debate_type") or "자유토론",
                side=side,
                winner_side=winner if winner in ("pro", "con") else None,
                result=result,
            )
        )
    return items


# ------------------------------------------------------------
# 전적 순위 (로그인한 회원만)
# ------------------------------------------------------------
@router.get("/stats", response_model=List[MemberStatsRow])
def member_stats(_: CurrentUser = Depends(get_current_user)):
    sb = get_supabase()
    users = fetch_all(lambda: sb.table("users").select("id,name,generation,major").order("id"))
    parts = fetch_all(
        lambda: sb.table("debate_participants")
        .select("user_id,debate_id,side")
        .not_.is_("user_id", "null")
        .order("id")
    )
    debates = fetch_all(lambda: sb.table("debates").select("id,winner_side").order("id"))
    winner_by_debate = {d["id"]: d.get("winner_side") for d in debates}

    stats: Dict[str, MemberStatsRow] = {
        u["id"]: MemberStatsRow(
            user_id=u["id"],
            name=(u.get("name") or "").strip() or "이름 미입력",
            generation=(u.get("generation") or "").strip(),
            major=(u.get("major") or "").strip(),
        )
        for u in users
    }

    for part in parts:
        row = stats.get(part.get("user_id") or "")
        if row is None:
            continue
        row.total += 1
        winner = winner_by_debate.get(part.get("debate_id"))
        if winner not in ("pro", "con"):
            continue
        if winner == part.get("side"):
            row.wins += 1
        else:
            row.losses += 1

    result = list(stats.values())
    for row in result:
        decided = row.wins + row.losses
        row.win_rate = round(row.wins / decided, 4) if decided else 0.0
    result.sort(key=lambda r: (-r.wins, -r.win_rate, -r.total, r.name))
    return result


# ------------------------------------------------------------
# 관리자: 회원 목록 / 권한 / 비밀번호 초기화 / 삭제
# ------------------------------------------------------------
@router.get("", response_model=List[MemberProfile])
def list_members(_: CurrentUser = Depends(get_admin_user)):
    sb = get_supabase()
    return fetch_all(lambda: sb.table("users").select(PROFILE_COLUMNS).order("name").order("id"))


def _get_member_or_404(user_id: str) -> dict:
    resp = get_supabase().table("users").select(PROFILE_COLUMNS).eq("id", user_id).limit(1).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="회원을 찾을 수 없습니다.")
    return resp.data[0]


@router.post("/{user_id}/reset-password")
def reset_member_password(user_id: str, _: CurrentUser = Depends(get_admin_user)):
    """비밀번호를 학번으로 초기화합니다. 다음 로그인 때 반드시 새 비밀번호로 바꿔야 합니다."""
    member = _get_member_or_404(user_id)
    student_id = (member.get("student_id") or "").strip()
    if not STUDENT_ID_PATTERN.match(student_id):
        raise HTTPException(status_code=400, detail="학번이 숫자 8자리가 아니라 초기 비밀번호로 쓸 수 없습니다.")
    sb = get_supabase()
    try:
        sb.auth.admin.update_user_by_id(user_id, {"password": student_id})
    except Exception:
        raise HTTPException(status_code=500, detail="비밀번호 초기화에 실패했습니다.")
    sb.table("users").update({"must_change_password": True}).eq("id", user_id).execute()
    return {"ok": True}


@router.patch("/{user_id}/role", response_model=MemberProfile)
def update_member_role(user_id: str, payload: RoleUpdateRequest, admin: CurrentUser = Depends(get_admin_user)):
    if user_id == admin.id and payload.role != "admin":
        raise HTTPException(status_code=400, detail="본인의 관리자 권한은 직접 해제할 수 없습니다.")
    _get_member_or_404(user_id)
    get_supabase().table("users").update({"role": payload.role}).eq("id", user_id).execute()
    return _get_member_or_404(user_id)


@router.delete("/{user_id}")
def delete_member(user_id: str, admin: CurrentUser = Depends(get_admin_user)):
    """계정을 삭제합니다. 토론 기록의 이름은 남고, 그 회원의 예약은 함께 지워집니다."""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="본인 계정은 삭제할 수 없습니다.")
    _get_member_or_404(user_id)
    try:
        get_supabase().auth.admin.delete_user(user_id)
    except Exception:
        raise HTTPException(status_code=500, detail="회원 삭제에 실패했습니다.")
    return {"ok": True}
