"""회원가입 / 로그인 / 비밀번호 변경."""
import time
from typing import Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from app import config
from app.db import get_supabase
from app.routers.members import STUDENT_ID_PATTERN, member_email
from app.schemas import ChangePasswordRequest, LoginRequest, LoginResponse, SignupRequest
from app.security import CurrentUser, get_pending_or_active_user

router = APIRouter()

_LOGIN_FAILED = "이름, 학번 또는 비밀번호가 올바르지 않습니다."
MIN_PASSWORD_LENGTH = 8

# 로그인 횟수 제한: 같은 (IP, 학번)으로 5분 동안 8번 넘게 실패하면 잠시 차단합니다.
# (서버 인스턴스별로 따로 세므로 '완화' 수준입니다. 회원가입에는 횟수 제한이 없습니다.)
_attempts: Dict[str, List[float]] = {}


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


def _recent(key: str, window: int) -> int:
    now = time.time()
    recent = [t for t in _attempts.get(key, []) if now - t < window]
    if recent:
        _attempts[key] = recent
    else:
        _attempts.pop(key, None)
    return len(recent)


def _record(key: str) -> None:
    if len(_attempts) > 5000:
        _attempts.clear()
    _attempts.setdefault(key, []).append(time.time())


def _validate_password(password: str, student_id: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"비밀번호는 {MIN_PASSWORD_LENGTH}자 이상이어야 합니다.")
    if password != password.strip():
        raise HTTPException(status_code=400, detail="비밀번호 앞뒤에 공백을 넣을 수 없습니다.")
    if student_id and student_id in password:
        raise HTTPException(status_code=400, detail="학번이 들어간 비밀번호는 사용할 수 없습니다.")


def _issue_tokens(email: str, password: str) -> Optional[dict]:
    """이메일/비밀번호가 맞으면 토큰을, 틀리면 None 을 돌려줍니다."""
    try:
        resp = httpx.post(
            f"{config.supabase_url()}/auth/v1/token",
            params={"grant_type": "password"},
            headers={"apikey": config.anon_key(), "Content-Type": "application/json"},
            json={"email": email, "password": password},
            timeout=15.0,
        )
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="인증 서버에 연결하지 못했습니다. 잠시 후 다시 시도해주세요.")
    if resp.status_code != 200:
        return None
    body = resp.json()
    if not body.get("access_token") or not body.get("refresh_token"):
        raise HTTPException(status_code=502, detail="인증 서버 응답이 올바르지 않습니다.")
    return body


@router.post("/signup", response_model=LoginResponse)
def signup(payload: SignupRequest):
    """누구나 이름 + 학번 + 비밀번호로 가입합니다. 관리자 승인 없이 바로 로그인됩니다."""
    name = payload.name.strip()
    student_id = payload.student_id.strip()
    if not name or len(name) > 30:
        raise HTTPException(status_code=400, detail="이름을 30자 이내로 입력해주세요.")
    if not STUDENT_ID_PATTERN.match(student_id):
        raise HTTPException(status_code=400, detail="학번은 숫자 8자리여야 합니다.")
    _validate_password(payload.password, student_id)

    sb = get_supabase()
    existing = sb.table("users").select("id").eq("student_id", student_id).limit(1).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail="이미 가입된 학번입니다. 로그인해주세요.")

    email = member_email(student_id)
    new_user_id: Optional[str] = None
    try:
        created = sb.auth.admin.create_user({"email": email, "password": payload.password, "email_confirm": True})
        new_user_id = created.user.id if created and created.user else None
        if not new_user_id:
            raise RuntimeError("no user id")
        sb.table("users").insert(
            {
                "id": new_user_id,
                "email": email,
                "name": name,
                "student_id": student_id,
                "major": payload.major.strip()[:50],
                "generation": payload.generation.strip()[:20],
                "role": "member",
                "must_change_password": False,
            }
        ).execute()
    except Exception:
        # 프로필 저장에 실패했으면 반쯤 만들어진 로그인 계정을 지워 다시 가입할 수 있게 합니다.
        if new_user_id:
            try:
                sb.auth.admin.delete_user(new_user_id)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail="가입에 실패했습니다. 이미 가입된 학번인지 확인하고 다시 시도해주세요.")

    tokens = _issue_tokens(email, payload.password)
    if tokens is None:
        raise HTTPException(status_code=502, detail="가입은 완료되었습니다. 로그인 화면에서 로그인해주세요.")
    return LoginResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        must_change_password=False,
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request):
    """이름 + 학번 + 비밀번호 로그인. 어느 항목이 틀렸는지는 알려주지 않습니다."""
    name = payload.name.strip()
    student_id = payload.student_id.strip()
    if not name or not student_id or not payload.password:
        raise HTTPException(status_code=400, detail="이름, 학번, 비밀번호를 모두 입력해주세요.")

    key = f"login|{_client_ip(request)}|{student_id}"
    if _recent(key, 300) >= 8:
        raise HTTPException(status_code=429, detail="로그인 시도가 너무 많습니다. 5분 뒤에 다시 시도해주세요.")

    found = (
        get_supabase()
        .table("users")
        .select("email,name,must_change_password")
        .eq("student_id", student_id)
        .limit(1)
        .execute()
    )
    row = found.data[0] if found.data else None
    if not row or (row.get("name") or "").strip() != name:
        _record(key)
        raise HTTPException(status_code=401, detail=_LOGIN_FAILED)

    tokens = _issue_tokens(row["email"], payload.password)
    if tokens is None:
        _record(key)
        raise HTTPException(status_code=401, detail=_LOGIN_FAILED)

    _attempts.pop(key, None)
    return LoginResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        must_change_password=bool(row.get("must_change_password")),
    )


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    user: CurrentUser = Depends(get_pending_or_active_user),
):
    _validate_password(payload.new_password, user.student_id)
    sb = get_supabase()
    try:
        sb.auth.admin.update_user_by_id(user.id, {"password": payload.new_password})
    except Exception:
        raise HTTPException(status_code=500, detail="비밀번호 변경에 실패했습니다. 잠시 후 다시 시도해주세요.")
    sb.table("users").update({"must_change_password": False}).eq("id", user.id).execute()
    return {"ok": True}
