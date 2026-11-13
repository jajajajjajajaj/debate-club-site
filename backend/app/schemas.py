"""요청/응답 모델."""
from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Side = Literal["pro", "con"]


# ---------- 인증 ----------
class LoginRequest(BaseModel):
    name: str
    student_id: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    must_change_password: bool


class SignupRequest(BaseModel):
    name: str
    student_id: str
    password: str
    major: str = ""
    generation: str = ""


class ChangePasswordRequest(BaseModel):
    new_password: str


# ---------- 회원 ----------
class MemberProfile(BaseModel):
    id: str
    email: str = ""
    name: str
    student_id: str
    major: str = ""
    generation: str = ""
    role: str = "member"
    must_change_password: bool = False


class RoleUpdateRequest(BaseModel):
    role: Literal["member", "admin"]


class MemberStatsRow(BaseModel):
    user_id: str
    name: str
    generation: str = ""
    major: str = ""
    wins: int = 0
    losses: int = 0
    total: int = 0
    win_rate: float = 0.0


class MyDebateItem(BaseModel):
    debate_id: str
    topic: str
    debate_date: date
    debate_type: str
    side: Side
    winner_side: Optional[Side] = None
    result: Literal["win", "loss", "pending"]


# ---------- 토론 ----------
class ParticipantInput(BaseModel):
    user_id: Optional[str] = None
    name: Optional[str] = None
    side: Side


class ParticipantOut(BaseModel):
    id: int
    user_id: Optional[str] = None
    name: str
    side: Side


class DebateInput(BaseModel):
    topic: str
    debate_date: date
    debate_type: str = "자유토론"
    winner_side: Optional[Side] = None
    notes: str = ""
    participants: List[ParticipantInput] = Field(default_factory=list)


class DebateOut(BaseModel):
    id: str
    topic: str
    debate_date: date
    debate_type: str
    winner_side: Optional[Side] = None
    notes: str = ""
    participants: List[ParticipantOut] = Field(default_factory=list)


class DebateResultRequest(BaseModel):
    winner_side: Optional[Side] = None


# ---------- 예약 ----------
class ReservationInput(BaseModel):
    title: str = ""
    starts_at: datetime
    ends_at: datetime
    debate_id: Optional[str] = None
    allow_simultaneous: bool = False
    # 관리자만 다른 회원 명의로 대리 예약 가능
    reserved_by: Optional[str] = None


class ReservationOut(BaseModel):
    id: str
    reserved_by: str
    reserved_by_name: str = ""
    title: str = ""
    starts_at: datetime
    ends_at: datetime
    debate_id: Optional[str] = None
    allow_simultaneous: bool = False


class ReservationCreateResponse(BaseModel):
    reservation: ReservationOut
    warn_opponent_booked: bool = False


class ReservationUpdate(BaseModel):
    title: str
