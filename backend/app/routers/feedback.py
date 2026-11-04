"""The contact form and in-app feedback. Messages are stored in the database; a honeypot field and a per-address limit keep bots out."""
from __future__ import annotations

from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import clock
from ..config import settings
from ..db import get_db
from ..models import Feedback
from ..schemas import FeedbackIn

router = APIRouter(tags=["feedback"])
_hits: dict[str, deque] = defaultdict(deque)


@router.post("/feedback", status_code=201)
def send_feedback(body: FeedbackIn, request: Request, db: Session = Depends(get_db)):
    if body.website:                       # a bot filled the hidden field: pretend it worked
        return {"ok": True}
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "?")).split(",")[0].strip()
    now = clock.now()
    q = _hits[ip]
    while q and (now - q[0]).total_seconds() > 3600:
        q.popleft()
    if len(q) >= settings.feedback_per_hour:
        raise HTTPException(429, "You have sent several messages already. Please try again later.")
    q.append(now)
    db.add(Feedback(name=(body.name or "").strip() or None, email=(body.email or "").strip().lower() or None, message=body.message.strip()))
    db.commit()
    return {"ok": True}
