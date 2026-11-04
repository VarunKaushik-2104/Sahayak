"""Database tables."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .clock import now
from .db import Base


def _now() -> datetime:
    return now()


class School(Base):
    __tablename__ = "schools"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str] = mapped_column(String(20), unique=True)               # students type this to join
    staff_code: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)   # colleagues use this to join as teachers
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_now, nullable=True)


class User(Base):
    """One table for the three roles. Students carry board, class, language and a 4-digit PIN; teachers and parents sign in with email + password."""
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(String(10), index=True)          # student | teacher | parent
    name: Mapped[str] = mapped_column(String(80))
    school_id: Mapped[int | None] = mapped_column(ForeignKey("schools.id"), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(200), nullable=True)
    link_code: Mapped[str | None] = mapped_column(String(12), nullable=True)   # students: a parent enters this to see their child's note
    pin_hash: Mapped[str | None] = mapped_column(String(200), nullable=True)
    failed_pins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    board: Mapped[str | None] = mapped_column(String(12), nullable=True)
    cls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lang: Mapped[str] = mapped_column(String(2), default="en")
    subject: Mapped[str] = mapped_column(String(10), default="Maths")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)    # demo classmates with no login
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (Index("ix_users_class", "school_id", "board", "cls"),
                      Index("ux_users_email_role", "email", "role", unique=True),
                      Index("ux_users_link_code", "link_code", unique=True))


class ParentChild(Base):
    __tablename__ = "parent_children"
    parent_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)


class Feedback(Base):
    """A message from the contact page or the app. Stored so it can be read and answered."""
    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    message: Mapped[str] = mapped_column(String(2000))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Mastery(Base):
    """P(student knows topic). The server's copy is authoritative: it is recomputed from raw answers."""
    __tablename__ = "mastery"
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    topic: Mapped[str] = mapped_column(String(24), primary_key=True)
    p: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class Attempt(Base):
    """One answered question. (student_id, cid) is unique, so replaying the same sync is harmless."""
    __tablename__ = "attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    cid: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(12))               # practice | check | placement | mock
    topic: Mapped[str] = mapped_column(String(24))
    qid: Mapped[str] = mapped_column(String(40))
    picked: Mapped[str] = mapped_column(String(400))
    ok: Mapped[bool] = mapped_column(Boolean)
    misconception: Mapped[str | None] = mapped_column(String(300), nullable=True)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (UniqueConstraint("student_id", "cid", name="uq_attempt_cid"),)


class MockResult(Base):
    __tablename__ = "mock_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    cid: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(80))
    subject: Mapped[str] = mapped_column(String(10))
    score: Mapped[int] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer)
    detail: Mapped[list] = mapped_column(JSON)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("student_id", "cid", name="uq_mock_cid"),)


class MisconceptionCount(Base):
    __tablename__ = "misconceptions"
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    label: Mapped[str] = mapped_column(String(300), primary_key=True)
    n: Mapped[int] = mapped_column(Integer, default=0)


class StudyMinutes(Base):
    __tablename__ = "study_minutes"
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    minutes: Mapped[float] = mapped_column(Float, default=0.0)


class TestPlan(Base):
    """The class test a teacher sets. Every student's plan and every parent's note follow it."""
    __tablename__ = "test_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    board: Mapped[str] = mapped_column(String(12))
    cls: Mapped[int] = mapped_column(Integer)
    subject: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(80), default="Unit Test")
    test_date: Mapped[date] = mapped_column(Date)
    chapters: Mapped[list] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (UniqueConstraint("school_id", "board", "cls", "subject", name="uq_test_scope"),)


class GroupOverride(Base):
    __tablename__ = "group_overrides"
    teacher_school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    group: Mapped[str] = mapped_column(String(10))


class Assignment(Base):
    """Practice a teacher sends to a group's phones."""
    __tablename__ = "assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    board: Mapped[str] = mapped_column(String(12))
    cls: Mapped[int] = mapped_column(Integer)
    subject: Mapped[str] = mapped_column(String(10))
    group: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(String(300))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
