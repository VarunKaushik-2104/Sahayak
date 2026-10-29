"""Online adaptive practice, for thin clients (and tests). The phone runs the same rules locally when offline."""
from __future__ import annotations

import random

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import clock
from ..content import Curriculum
from ..db import get_db
from ..deps import curriculum, require_role
from ..engine import practice as eng
from ..models import Attempt, User
from ..schemas import AnswerIn, NextIn
from ..services import state

router = APIRouter(prefix="/practice", tags=["practice"])
Student = Depends(require_role("student"))


def _public(topic: str, q: dict) -> dict:
    opts = [o["t"] for o in q["o"]]
    random.shuffle(opts)
    return {"qid": q["id"], "topic": topic, "level": q["lvl"], "q": q["q"], "options": opts}


def _need(cur: Curriculum, topic: str) -> None:
    if not cur.has(topic):
        raise HTTPException(422, f"Unknown topic {topic}")


@router.post("/next")
def next_question(body: NextIn, user: User = Student, db: Session = Depends(get_db), cur: Curriculum = Depends(curriculum)):
    _need(cur, body.target)
    focus = body.focus or body.target
    _need(cur, focus)
    for t in body.chapter_topics or []:
        _need(cur, t)
    P = state.load_P(db, user.id)
    step = eng.next_step(cur, P, set(body.asked), body.target, focus, body.answered, body.chapter_topics)
    if step.phase == "solve":
        t, q = step.question
        return {"phase": "solve", "focus": step.focus, "question": _public(t, q), "mastery": {t: P.get(t, 0.5)}}
    return {"phase": "check", "focus": step.focus, "questions": [_public(t, q) for t, q in step.check]}


@router.post("/answer")
def answer(body: AnswerIn, user: User = Student, db: Session = Depends(get_db), cur: Curriculum = Depends(curriculum)):
    """Mark, update mastery, and say where to go next (including back through a prerequisite)."""
    m = eng.mark(cur, body.qid, body.pick)
    if not m:
        raise HTTPException(422, "Unknown question or option")
    _need(cur, body.target)
    focus = body.focus or body.target
    _need(cur, focus)
    dup = db.query(Attempt).filter(Attempt.student_id == user.id, Attempt.cid == body.cid).first()
    P = state.load_P(db, user.id)
    asked = set(body.asked)
    if dup:       # a retried request: report the same verdict, change nothing
        return {"ok": dup.ok, "why": m.why, "right": m.right, "misconception": m.misconception, "duplicate": True,
                "focus": focus, "trace_to": None, "back_to_target": False, "mastery": P.get(m.topic, 0.5)}
    res = eng.apply_answer(cur, P, asked, body.target, focus, m, in_check=body.phase == "check")
    ts = clock.now()
    db.add(Attempt(student_id=user.id, cid=body.cid, kind="check" if body.phase == "check" else "practice", topic=m.topic,
                   qid=m.qid, picked=body.pick, ok=m.ok, misconception=m.misconception, answered_at=ts))
    if m.misconception:
        state.bump_misc(db, user.id, m.misconception)
    state.add_minutes(db, user.id, clock.local_date(ts), 1.2)
    state.save_P(db, user.id, P, {m.topic})
    user.last_sync_at = ts
    db.commit()
    out = {"ok": m.ok, "why": m.why, "right": m.right, "misconception": m.misconception, "duplicate": False,
           "focus": res.focus, "back_to_target": res.back_to_target, "mastery_before": round(res.before, 4),
           "mastery": round(res.after, 4), "trace_to": None}
    if res.trace_to:
        out["trace_to"] = {"topic": res.trace_to, "name": cur.T[res.trace_to]["name"], "mastery": round(P.get(res.trace_to, 0.5), 4),
                           "needs_lesson": P.get(res.trace_to, 0.5) < eng.TRACE_WEAK}
    return out
