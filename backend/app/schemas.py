"""Request and response bodies."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Board = Literal["CBSE", "ICSE", "TELANGANA"]
Subject = Literal["Maths", "Science"]
Lang = Literal["en", "hi", "te"]


class RegisterStudent(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    pin: str = Field(pattern=r"^\d{4}$")
    board: Board
    cls: int = Field(ge=6, le=10)
    lang: Lang = "en"
    school_code: str | None = Field(default=None, max_length=20)

    @field_validator("name")
    @classmethod
    def _clean(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("name is empty")
        return v


class StudentLogin(BaseModel):
    student_id: int
    pin: str = Field(pattern=r"^\d{4}$")


class OtpRequest(BaseModel):
    mobile: str = Field(min_length=10, max_length=15)
    role: Literal["teacher", "parent"]


class OtpVerify(OtpRequest):
    code: str = Field(pattern=r"^\d{6}$")


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str
    user: dict


class ProfilePatch(BaseModel):
    lang: Lang | None = None
    subject: Subject | None = None


# ---- sync -------------------------------------------------------------------------
class PlacementAnswer(BaseModel):
    qid: str = Field(max_length=40)
    pick: str = Field(max_length=400)


class MockRow(BaseModel):
    kind: Literal["mcq", "steps"]
    qid: str | None = Field(default=None, max_length=40)
    topic: str | None = Field(default=None, max_length=24)
    pick: str | None = Field(default=None, max_length=400)
    picks: list[str] | None = None


class SyncEvent(BaseModel):
    cid: str = Field(min_length=6, max_length=64)
    type: Literal["answer", "placement", "mock"]
    ts: datetime
    kind: Literal["practice", "check"] = "practice"      # for type=answer
    qid: str | None = Field(default=None, max_length=40)
    pick: str | None = Field(default=None, max_length=400)
    answers: list[PlacementAnswer] | None = Field(default=None, max_length=12)
    rows: list[MockRow] | None = Field(default=None, max_length=12)
    name: str | None = Field(default=None, max_length=80)
    subject: Subject | None = None
    minutes: float | None = Field(default=None, ge=0, le=180)


class SyncIn(BaseModel):
    events: list[SyncEvent] = Field(max_length=500)


# ---- practice (online, stateless) ---------------------------------------------------
class NextIn(BaseModel):
    target: str
    focus: str | None = None
    answered: int = Field(default=0, ge=0, le=50)
    asked: list[str] = Field(default_factory=list, max_length=200)
    chapter_topics: list[str] | None = Field(default=None, max_length=12)


class AnswerIn(BaseModel):
    cid: str = Field(min_length=6, max_length=64)
    qid: str
    pick: str = Field(max_length=400)
    target: str
    focus: str | None = None
    answered: int = Field(default=0, ge=0, le=50)
    asked: list[str] = Field(default_factory=list, max_length=200)
    phase: Literal["solve", "check"] = "solve"


class MockSubmit(BaseModel):
    cid: str = Field(min_length=6, max_length=64)
    name: str = Field(default="Mock test", max_length=80)
    subject: Subject
    rows: list[MockRow] = Field(max_length=12)
    minutes: float = Field(default=0, ge=0, le=180)


# ---- teacher ------------------------------------------------------------------------
class TestIn(BaseModel):
    board: Board
    cls: int = Field(ge=6, le=10)
    subject: Subject
    name: str = Field(default="Unit Test", min_length=1, max_length=80)
    date: date
    chapters: list[str] = Field(min_length=1, max_length=20)


class GroupIn(BaseModel):
    student_id: int
    group: Literal["extend", "practise", "basics"]


class AssignIn(BaseModel):
    board: Board
    cls: int = Field(ge=6, le=10)
    subject: Subject
    group: Literal["extend", "practise", "basics"]
