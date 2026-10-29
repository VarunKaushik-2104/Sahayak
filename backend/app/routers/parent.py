"""A parent sees a plain note about their own child, in their language. No marks, no rank, no other children."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import clock
from ..content import Curriculum
from ..db import get_db
from ..deps import curriculum, require_role
from ..engine.parent import LANGS, build_note
from ..models import ParentChild, User
from ..services import state

router = APIRouter(prefix="/parent", tags=["parent"])
Parent = Depends(require_role("parent"))


@router.get("/children")
def children(user: User = Parent, db: Session = Depends(get_db)):
    return [{"id": c.id, "name": c.name, "cls": c.cls, "board": c.board, "subject": c.subject} for c in state.children_of(db, user.id)]


@router.get("/note")
def note(student_id: int = Query(...), lang: str = Query("en"), user: User = Parent,
         db: Session = Depends(get_db), cur: Curriculum = Depends(curriculum)):
    if lang not in LANGS:
        raise HTTPException(422, "lang must be en, hi or te")
    if db.get(ParentChild, (user.id, student_id)) is None:
        raise HTTPException(403, "That child is not linked to your account")
    s = db.get(User, student_id)
    today = clock.today()
    tp = state.get_or_create_test(db, cur, s.school_id, s.board, s.cls, s.subject)
    tv = state.test_view(cur, tp, today)
    db.commit()
    mins = state.last7(db, s.id, today)
    n = build_note(cur, name=s.name, subject=s.subject, lang=lang, P=state.load_P(db, s.id), misc=state.load_misc(db, s.id),
                   minutes_last7=mins, test={"name": tv["name"], "date": tv["date"], "chapters": tv["chapters"], "topics": tv["topics"]},
                   today=today)
    return n | {"student": {"id": s.id, "name": s.name, "cls": s.cls, "subject": s.subject},
                "minutes_by_day": [{"date": (today - timedelta(days=6 - i)).isoformat(), "minutes": m} for i, m in enumerate(mins)],
                "last_sync": s.last_sync_at.isoformat() if s.last_sync_at else None}
