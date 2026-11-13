"""인증/권한 검사.

- 토큰 검증: SUPABASE_JWT_SECRET 이 있으면 직접(HS256) 검증하고,
  없으면 Supabase Auth 서버(/auth/v1/user)에 물어봅니다.
- 권한(관리자 여부, 비밀번호 변경 필요 여부)은 항상 DB(public.users)에서 읽습니다.
  토큰 안의 user_metadata 는 사용자가 바꿀 수 있으므로 믿지 않습니다.
"""
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import httpx
import jwt
from fastapi import Depends, Header, HTTPException

from app import config
from app.db import get_supabase

_TOKEN_CACHE: Dict[str, Tuple[str, float]] = {}
_TOKEN_CACHE_SECONDS = 60
_TOKEN_CACHE_MAX = 2000


@dataclass
class CurrentUser:
    id: str
    name: str
    student_id: str
    role: str
    must_change_password: bool

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def _verify_locally(token: str, secret: str) -> str:
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"], audience="authenticated")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="로그인이 만료되었습니다. 다시 로그인해주세요.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="유효하지 않은 로그인 정보입니다.")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="유효하지 않은 로그인 정보입니다.")
    return str(user_id)


def _verify_remotely(token: str) -> str:
    now = time.time()
    cached = _TOKEN_CACHE.get(token)
    if cached and cached[1] > now:
        return cached[0]

    try:
        resp = httpx.get(
            f"{config.supabase_url()}/auth/v1/user",
            headers={"Authorization": f"Bearer {token}", "apikey": config.anon_key()},
            timeout=10.0,
        )
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="인증 서버에 연결하지 못했습니다. 잠시 후 다시 시도해주세요.")
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="로그인이 만료되었거나 유효하지 않습니다.")
    user_id = (resp.json() or {}).get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="유효하지 않은 로그인 정보입니다.")

    if len(_TOKEN_CACHE) >= _TOKEN_CACHE_MAX:
        _TOKEN_CACHE.clear()
    _TOKEN_CACHE[token] = (str(user_id), now + _TOKEN_CACHE_SECONDS)
    return str(user_id)


def _user_id_from_header(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    token = authorization[len("Bearer ") :].strip()
    if not token:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    secret = config.jwt_secret()
    if secret:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="유효하지 않은 로그인 정보입니다.")
        if header.get("alg") == "HS256":
            return _verify_locally(token, secret)
    return _verify_remotely(token)


def _load_user(user_id: str) -> CurrentUser:
    resp = (
        get_supabase()
        .table("users")
        .select("id,name,student_id,role,must_change_password")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=403, detail="등록된 회원이 아닙니다. 관리자에게 문의해주세요.")
    row = resp.data[0]
    return CurrentUser(
        id=row["id"],
        name=row.get("name") or "",
        student_id=row.get("student_id") or "",
        role=row.get("role") or "member",
        must_change_password=bool(row.get("must_change_password")),
    )


def get_pending_or_active_user(authorization: Optional[str] = Header(default=None)) -> CurrentUser:
    """로그인만 되어 있으면 통과 (비밀번호 변경 전이어도 허용). 내 정보 조회·비밀번호 변경 전용."""
    return _load_user(_user_id_from_header(authorization))


def get_current_user(user: CurrentUser = Depends(get_pending_or_active_user)) -> CurrentUser:
    """일반 API용. 초기 비밀번호(학번)를 아직 바꾸지 않은 계정은 서버에서 막습니다."""
    if user.must_change_password:
        raise HTTPException(status_code=403, detail="PASSWORD_CHANGE_REQUIRED")
    return user


def get_admin_user(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    return user
