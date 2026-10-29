"""Reading and writing a student's learning state."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import clock
from ..content import Curriculum
from ..engine.teacher import Row, STALE_DAYS, group_of
from ..models import (GroupOverride, Mastery, MisconceptionCount, ParentChild, StudyMinutes, TestPlan, User)


def load_P(db: Session, student_id: int) -> dict[str, float]:
    return {m.topic: m.p for m in db.scalars(select(Mastery).where(Mastery.student_id == student_id))}


def save_P(db: Session, student_id: int, P: dict[str, float], changed: set[str]) -> None:
    existing = {m.topic: m for m in db.scalars(select(Mastery).where(Mastery.student_id == student_id, Mastery.topic.in_(changed)))} if changed else {}
    for t in changed:
        if t in existing:
            existing[t].p = P[t]
        else:
            db.add(Mastery(student_id=student_id, topic=t, p=P[t]))


def load_misc(db: Session, student_id: int) -> dict[str, int]:
    return {m.label: m.n for m in db.scalars(select(MisconceptionCount).where(MisconceptionCount.student_id == student_id))}


def bump_misc(db: Session, student_id: int, label: str) -> None:
    row = db.get(MisconceptionCount, (student_id, label))
    if row:
        row.n += 1
    else:
        db.add(MisconceptionCount(student_id=student_id, label=label, n=1))
        db.flush()    # autoflush is off: make the new row visible to the next db.get


def add_minutes(db: Session, student_id: int, day: date, mins: float) -> None:
    row = db.get(StudyMinutes, (student_id, day))
    if row:
        row.minutes += mins
    else:
        db.add(StudyMinutes(student_id=student_id, day=day, minutes=mins))
        db.flush()


def minutes_by_day(db: Session, student_id: int, today: date, span: int = 7) -> dict[str, float]:
    start = today - timedelta(days=span - 1)
    rows = db.scalars(select(StudyMinutes).where(StudyMinutes.student_id == student_id, StudyMinutes.day >= start))
    return {r.day.isoformat(): round(r.minutes, 1) for r in rows}


def last7(db: Session, student_id: int, today: date) -> list[int]:
    m = minutes_by_day(db, student_id, today)
    return [round(m.get((today - timedelta(days=6 - i)).isoformat(), 0)) for i in range(7)]


# ---- tests ---------------------------------------------------------------------------
def get_or_create_test(db: Session, cur: Curriculum, school_id: int, board: str, cls: int, subject: str) -> TestPlan:
    tp = db.scalar(select(TestPlan).where(TestPlan.school_id == school_id, TestPlan.board == board,
                                          TestPlan.cls == cls, TestPlan.subject == subject))
    if tp is None:
        chs = cur.chapters(board, cls, subject)
        tp = TestPlan(school_id=school_id, board=board, cls=cls, subject=subject, name="Unit Test",
                      test_date=clock.today() + timedelta(days=6), chapters=[c["name"] for c in chs[:2]])
        db.add(tp)
        db.flush()
    return tp


def test_view(cur: Curriculum, tp: TestPlan, today: date) -> dict:
    allch = cur.chapters(tp.board, tp.cls, tp.subject)
    chosen = [c for n in tp.chapters for c in allch if c["name"] == n] or allch[:1]
    return {"name": tp.name, "date": tp.test_date.isoformat(), "days": (tp.test_date - today).days,
            "chapters": [c["name"] for c in chosen], "chapter_objs": chosen,
            "topics": cur.chapter_topics(chosen), "available_chapters": [c["name"] for c in allch]}


def public_test(tv: dict) -> dict:
    return {k: v for k, v in tv.items() if k != "chapter_objs"}


# ---- class rows ----------------------------------------------------------------------
def class_rows(db: Session, cur: Curriculum, school_id: int, board: str, cls: int) -> list[Row]:
    students = list(db.scalars(select(User).where(User.role == "student", User.school_id == school_id,
                                                  User.board == board, User.cls == cls).order_by(User.is_sample, User.id)))
    if not students:
        return []
    ids = [s.id for s in students]
    P: dict[int, dict[str, float]] = {i: {} for i in ids}
    for m in db.scalars(select(Mastery).where(Mastery.student_id.in_(ids))):
        P[m.student_id][m.topic] = m.p
    now = clock.now()
    rows = []
    for s in students:
        ls = s.last_sync_at
        if ls is not None and ls.tzinfo is None:
            from datetime import timezone
            ls = ls.replace(tzinfo=timezone.utc)
        stale = ls is None or (now - ls) >= timedelta(days=STALE_DAYS)
        rows.append(Row(id=s.id, name=s.name, P=P[s.id], last_sync=ls.isoformat() if ls else None, stale=stale, sample=s.is_sample))
    return rows


def group_map(db: Session, cur: Curriculum, school_id: int, rows: list[Row], test_topics: list[str]) -> dict[int, str]:
    over = {g.student_id: g.group for g in db.scalars(select(GroupOverride).where(GroupOverride.teacher_school_id == school_id))}
    return {r.id: over.get(r.id) or group_of(cur, r.P, test_topics) for r in rows}


def student_group(db: Session, cur: Curriculum, s: User, tv: dict) -> str:
    P = load_P(db, s.id)
    over = db.get(GroupOverride, (s.school_id, s.id))
    return over.group if over else group_of(cur, P, tv["topics"])


def children_of(db: Session, parent_id: int) -> list[User]:
    ids = [r.student_id for r in db.scalars(select(ParentChild).where(ParentChild.parent_id == parent_id))]
    return list(db.scalars(select(User).where(User.id.in_(ids)))) if ids else []
