"""토론 기록. 조회는 로그인한 회원, 작성/수정/삭제는 관리자."""
from datetime import date
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import chunked, fetch_all, get_supabase
from app.schemas import DebateInput, DebateOut, DebateResultRequest, ParticipantInput, ParticipantOut
from app.security import CurrentUser, get_admin_user, get_current_user

router = APIRouter()

DEBATE_COLUMNS = "id,topic,debate_date,debate_type,winner_side,notes"


def _attach_participants(debates: List[dict]) -> List[DebateOut]:
    if not debates:
        return []
    sb = get_supabase()
    by_debate: Dict[str, List[ParticipantOut]] = {d["id"]: [] for d in debates}
    for ids in chunked(list(by_debate.keys()), 100):
        rows = fetch_all(
            lambda ids=ids: sb.table("debate_participants")
            .select("id,debate_id,user_id,participant_name,side")
            .in_("debate_id", ids)
            .order("id")
        )
        for row in rows:
            by_debate[row["debate_id"]].append(
                ParticipantOut(
                    id=row["id"],
                    user_id=row.get("user_id"),
                    name=row.get("participant_name") or "",
                    side=row["side"],
                )
            )
    return [
        DebateOut(
            id=d["id"],
            topic=d.get("topic") or "",
            debate_date=d["debate_date"],
            debate_type=d.get("debate_type") or "자유토론",
            winner_side=d.get("winner_side") if d.get("winner_side") in ("pro", "con") else None,
            notes=d.get("notes") or "",
            participants=by_debate[d["id"]],
        )
        for d in debates
    ]


def _get_debate_or_404(debate_id: str) -> dict:
    resp = get_supabase().table("debates").select(DEBATE_COLUMNS).eq("id", debate_id).limit(1).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="토론을 찾을 수 없습니다.")
    return resp.data[0]


def _semester_range(year: int, semester: Optional[int]) -> tuple:
    """1학기: 3~8월, 2학기: 9월~다음 해 2월. 학기 미지정이면 그 해 1~12월."""
    if semester == 1:
        return date(year, 3, 1), date(year, 9, 1)
    if semester == 2:
        return date(year, 9, 1), date(year + 1, 3, 1)
    return date(year, 1, 1), date(year + 1, 1, 1)


@router.get("", response_model=List[DebateOut])
def list_debates(
    year: Optional[int] = Query(default=None, ge=2000, le=2100),
    semester: Optional[int] = Query(default=None, ge=1, le=2),
    debate_type: Optional[str] = Query(default=None, max_length=50),
    _: CurrentUser = Depends(get_current_user),
):
    sb = get_supabase()

    def build():
        query = sb.table("debates").select(DEBATE_COLUMNS)
        if year is not None:
            start, end_exclusive = _semester_range(year, semester)
            query = query.gte("debate_date", start.isoformat()).lt("debate_date", end_exclusive.isoformat())
        if debate_type:
            query = query.eq("debate_type", debate_type)
        return query.order("debate_date", desc=True).order("id")

    return _attach_participants(fetch_all(build))


@router.get("/{debate_id}", response_model=DebateOut)
def get_debate(debate_id: str, _: CurrentUser = Depends(get_current_user)):
    return _attach_participants([_get_debate_or_404(debate_id)])[0]


def _participant_rows(debate_id: str, participants: List[ParticipantInput]) -> List[dict]:
    """입력을 검증하고 DB에 넣을 행으로 바꿉니다. 회원이면 현재 이름을 함께 저장합니다."""
    member_ids = [p.user_id for p in participants if p.user_id]
    if len(member_ids) != len(set(member_ids)):
        raise HTTPException(status_code=400, detail="같은 회원이 두 번 들어가 있습니다.")

    name_by_id: Dict[str, str] = {}
    if member_ids:
        sb = get_supabase()
        for ids in chunked(member_ids, 100):
            resp = sb.table("users").select("id,name").in_("id", ids).execute()
            for row in resp.data or []:
                name_by_id[row["id"]] = row.get("name") or ""
        missing = [m for m in member_ids if m not in name_by_id]
        if missing:
            raise HTTPException(status_code=400, detail="존재하지 않는 회원이 참가자에 포함되어 있습니다.")

    rows: List[dict] = []
    for p in participants:
        if p.user_id:
            name = name_by_id[p.user_id]
        else:
            name = (p.name or "").strip()
            if not name:
                raise HTTPException(status_code=400, detail="참가자는 회원을 고르거나 이름을 입력해야 합니다.")
        rows.append({"debate_id": debate_id, "user_id": p.user_id, "participant_name": name, "side": p.side})
    return rows


def _debate_fields(payload: DebateInput) -> dict:
    topic = payload.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="논제를 입력해주세요.")
    return {
        "topic": topic,
        "debate_date": payload.debate_date.isoformat(),
        "debate_type": payload.debate_type.strip() or "자유토론",
        "winner_side": payload.winner_side,
        "notes": payload.notes.strip(),
    }


@router.post("", response_model=DebateOut)
def create_debate(payload: DebateInput, admin: CurrentUser = Depends(get_admin_user)):
    fields = _debate_fields(payload)
    # 참가자 검증을 먼저 해서, 잘못된 입력이면 아무것도 저장하지 않습니다.
    _participant_rows("00000000-0000-0000-0000-000000000000", payload.participants)

    sb = get_supabase()
    resp = sb.table("debates").insert({**fields, "created_by": admin.id}).execute()
    if not resp.data:
        raise HTTPException(status_code=500, detail="토론 저장에 실패했습니다.")
    debate_id = resp.data[0]["id"]

    rows = _participant_rows(debate_id, payload.participants)
    if rows:
        try:
            sb.table("debate_participants").insert(rows).execute()
        except Exception:
            sb.table("debates").delete().eq("id", debate_id).execute()
            raise HTTPException(status_code=500, detail="참가자 저장에 실패해 토론을 저장하지 않았습니다.")
    return get_debate_unchecked(debate_id)


def get_debate_unchecked(debate_id: str) -> DebateOut:
    return _attach_participants([_get_debate_or_404(debate_id)])[0]


@router.put("/{debate_id}", response_model=DebateOut)
def update_debate(debate_id: str, payload: DebateInput, _: CurrentUser = Depends(get_admin_user)):
    _get_debate_or_404(debate_id)
    fields = _debate_fields(payload)
    rows = _participant_rows(debate_id, payload.participants)

    sb = get_supabase()
    previous = fetch_all(
        lambda: sb.table("debate_participants")
        .select("debate_id,user_id,participant_name,side")
        .eq("debate_id", debate_id)
        .order("id")
    )
    sb.table("debates").update(fields).eq("id", debate_id).execute()
    sb.table("debate_participants").delete().eq("debate_id", debate_id).execute()
    if rows:
        try:
            sb.table("debate_participants").insert(rows).execute()
        except Exception:
            # 새 참가자 저장에 실패하면 이전 참가자를 되돌려 놓습니다.
            if previous:
                sb.table("debate_participants").insert(previous).execute()
            raise HTTPException(status_code=500, detail="참가자 저장에 실패했습니다. 참가자는 이전 상태로 되돌렸습니다.")
    return get_debate_unchecked(debate_id)


@router.patch("/{debate_id}/result", response_model=DebateOut)
def set_result(debate_id: str, payload: DebateResultRequest, _: CurrentUser = Depends(get_admin_user)):
    """승리 측을 기록합니다. null 을 보내면 '미정'으로 되돌립니다."""
    _get_debate_or_404(debate_id)
    get_supabase().table("debates").update({"winner_side": payload.winner_side}).eq("id", debate_id).execute()
    return get_debate_unchecked(debate_id)


@router.delete("/{debate_id}")
def delete_debate(debate_id: str, _: CurrentUser = Depends(get_admin_user)):
    _get_debate_or_404(debate_id)
    get_supabase().table("debates").delete().eq("id", debate_id).execute()
    return {"ok": True}
