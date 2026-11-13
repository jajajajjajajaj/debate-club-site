"""Supabase(service_role) 클라이언트.

주의: 이 클라이언트로는 절대 auth.sign_in_* 을 호출하지 않습니다.
(로그인하면 클라이언트의 권한이 그 사용자 것으로 바뀌어 버립니다.)
"""
import time
from typing import Any, Callable, Dict, List, Optional

from supabase import Client, create_client

from app import config

_client: Optional[Client] = None
_created_at: float = 0.0
_TTL_SECONDS = 300  # 오래된 연결이 끊기는 문제를 피하려고 주기적으로 새로 만듭니다.

PAGE_SIZE = 1000


def get_supabase() -> Client:
    global _client, _created_at
    now = time.time()
    if _client is None or now - _created_at > _TTL_SECONDS:
        _client = create_client(config.supabase_url(), config.service_role_key())
        _created_at = now
    return _client


def fetch_all(build_query: Callable[[], Any]) -> List[Dict[str, Any]]:
    """PostgREST 의 기본 1000행 제한을 넘는 테이블을 끝까지 읽습니다."""
    rows: List[Dict[str, Any]] = []
    start = 0
    while True:
        resp = build_query().range(start, start + PAGE_SIZE - 1).execute()
        batch = resp.data or []
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            return rows
        start += PAGE_SIZE


def chunked(items: List[Any], size: int = 100) -> List[List[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]
