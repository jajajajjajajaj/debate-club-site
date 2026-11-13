"""환경 변수 로딩."""
import os
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1].strip()
    return value or default


def _require(name: str) -> str:
    value = _env(name)
    if not value:
        raise RuntimeError(f"환경 변수 {name} 이(가) 설정되지 않았습니다.")
    return value


def supabase_url() -> str:
    return _require("SUPABASE_URL").rstrip("/")


def service_role_key() -> str:
    return _require("SUPABASE_SERVICE_ROLE_KEY")


def anon_key() -> str:
    # 로그인(비밀번호 확인) 요청에 쓰는 공개 키. 없으면 서비스 키로 대신합니다.
    return _env("SUPABASE_ANON_KEY") or service_role_key()


def jwt_secret() -> Optional[str]:
    return _env("SUPABASE_JWT_SECRET")


def member_email_domain() -> str:
    return _env("MEMBER_EMAIL_DOMAIN", "member.debate-club.local") or "member.debate-club.local"


def max_concurrent_reservations() -> int:
    try:
        return max(1, int(_env("MAX_CONCURRENT_RESERVATIONS", "2") or "2"))
    except ValueError:
        return 2


def allowed_origins() -> List[str]:
    raw = _env("ALLOWED_ORIGINS", "") or ""
    origins = [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
    for dev in ("http://localhost:5173", "http://127.0.0.1:5173"):
        if dev not in origins:
            origins.append(dev)
    return origins
