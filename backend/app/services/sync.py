"""Apply a batch of offline events to the authoritative state.

The phone sends *what the student picked*, never what it thinks the result was. The server marks each answer against the
curriculum, so a tampered client cannot invent mastery. Every event has a client id; replaying one is harmless.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import clock
from ..content import Curriculum
from ..engine import mock as mock_engine
from ..engine.mastery import nudge
from ..engine.practice import mark
from ..models import Attempt, MockResult, User
from ..schemas import SyncEvent
from . import state

MINUTES_PER_ANSWER = 1.2
MAX_SKEW_HOURS = 24 * 14


@dataclass
class SyncReport:
    accepted: int = 0
    duplicates: int = 0
    rejected: list[dict] = field(default_factory=list)


def _utc(dt):
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _clamp_ts(ts):
    """A phone clock can be wrong. Never trust a time in the future or older than two weeks."""
    now = clock.now()
    ts = _utc(ts)
    if ts > now:
        return now
    if (now - ts).total_seconds() > MAX_SKEW_HOURS * 3600:
        return now
    return ts


def apply_events(db: Session, cur: Curriculum, student: User, events: list[SyncEvent]) -> tuple[SyncReport, dict[str, float]]:
    rep = SyncReport()
    P = state.load_P(db, student.id)
    changed: set[str] = set()
    seen_cids = {c for (c,) in db.execute(select(Attempt.cid).where(Attempt.student_id == student.id))}
    seen_cids |= {c for (c,) in db.execute(select(MockResult.cid).where(MockResult.student_id == student.id))}
    seen_cids |= {c.split(":")[0] for c in seen_cids if ":" in c}   # placement answers are stored as <cid>:<n>

    for ev in sorted(events, key=lambda e: _utc(e.ts)):
        if ev.cid in seen_cids:
            rep.duplicates += 1
            continue
        ts = _clamp_ts(ev.ts)
        day = clock.local_date(ts)
        try:
            if ev.type == "answer":
                m = mark(cur, ev.qid or "", ev.pick or "")
                if not m:
                    raise ValueError("unknown question or option")
                P[m.topic] = nudge(P.get(m.topic, 0.5), m.ok)
                changed.add(m.topic)
                db.add(Attempt(student_id=student.id, cid=ev.cid, kind=ev.kind, topic=m.topic, qid=m.qid, picked=ev.pick,
                               ok=m.ok, misconception=m.misconception, answered_at=ts))
                if m.misconception:
                    state.bump_misc(db, student.id, m.misconception)
                state.add_minutes(db, student.id, day, MINUTES_PER_ANSWER)
            elif ev.type == "placement":
                _placement(db, cur, student, P, changed, ev, ts, day)
            elif ev.type == "mock":
                _mock(db, cur, student, P, changed, ev, ts, day)
            seen_cids.add(ev.cid)
            rep.accepted += 1
        except ValueError as e:
            rep.rejected.append({"cid": ev.cid, "reason": str(e)})
    state.save_P(db, student.id, P, changed)
    student.last_sync_at = clock.now()
    return rep, P


def _placement(db, cur, student, P, changed, ev, ts, day):
    answers = ev.answers or []
    if not 1 <= len(answers) <= 8:
        raise ValueError("placement needs 1 to 8 answers")
    marked = []
    for a in answers:
        m = mark(cur, a.qid, a.pick)
        if not m:
            raise ValueError("unknown question or option")
        marked.append(m)
    had = set(P)
    for i, m in enumerate(marked):
        P[m.topic] = nudge(0.5, m.ok)       # a placement answer sets the starting picture for that topic
        changed.add(m.topic)
        db.add(Attempt(student_id=student.id, cid=f"{ev.cid}:{i}", kind="placement", topic=m.topic, qid=m.qid,
                       picked=m.picked, ok=m.ok, misconception=m.misconception, answered_at=ts))
        if m.misconception:
            state.bump_misc(db, student.id, m.misconception)
    for m in marked:    # spread what we learned to related topics that have no data yet
        v = P[m.topic]
        for t, info in cur.T.items():
            if t not in had and t not in P and info["sub"] == cur.T[m.topic]["sub"] and (cur.depends_on(t, m.topic) or cur.depends_on(m.topic, t)):
                P[t] = 0.5 + (v - 0.5) * 0.5
                changed.add(t)
    state.add_minutes(db, student.id, day, MINUTES_PER_ANSWER * len(marked))


def _mock(db, cur, student, P, changed, ev, ts, day) -> None:
    marked = []
    for r in ev.rows or []:
        row = mock_engine.mark_row(cur, r.model_dump())
        if row is None:
            raise ValueError("mock row does not match the curriculum")
        marked.append(row)
    if not marked:
        raise ValueError("mock has no rows")
    score = sum(r["got"] for r in marked)
    total = sum(r["marks"] for r in marked)
    for r in marked:
        P[r["topic"]] = nudge(P.get(r["topic"], 0.5), r["got"] == r["marks"])
        changed.add(r["topic"])
        for label in r["misconceptions"]:
            state.bump_misc(db, student.id, label)
    db.add(MockResult(student_id=student.id, cid=ev.cid, name=ev.name or "Mock test", subject=ev.subject or student.subject,
                      score=score, total=total, detail=marked, taken_at=ts))
    state.add_minutes(db, student.id, day, ev.minutes if ev.minutes else 1.0)
