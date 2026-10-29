"""Sign-in. Students: profile + 4-digit PIN (locks after repeated misses). Teachers and parents: mobile + one-time code."""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import clock
from ..config import settings
from ..db import get_db
from ..deps import current_user
from ..models import OtpCode, School, User
from ..schemas import OtpRequest, OtpVerify, RegisterStudent, StudentLogin, TokenOut
from ..security import hash_secret, make_otp, make_token, normalise_mobile, verify_secret

router = APIRouter(prefix="/auth", tags=["auth"])
_otp_hits: dict[str, deque] = defaultdict(deque)


def public_user(u: User) -> dict:
    d = {"id": u.id, "role": u.role, "name": u.name}
    if u.role == "student":
        d |= {"board": u.board, "cls": u.cls, "lang": u.lang, "subject": u.subject}
    return d


def _token_out(u: User) -> TokenOut:
    tok, ttl = make_token(u.id, u.role)
    return TokenOut(access_token=tok, expires_in=ttl, role=u.role, user=public_user(u))


def _self_study_school(db: Session) -> School:
    s = db.scalar(select(School).where(School.code == "SELF"))
    if not s:
        s = School(name="Self-study", code="SELF")
        db.add(s)
        db.flush()
    return s


@router.post("/register-student", response_model=TokenOut, status_code=201)
def register_student(body: RegisterStudent, db: Session = Depends(get_db)):
    if body.school_code:
        school = db.scalar(select(School).where(School.code == body.school_code.strip().upper()))
        if not school:
            raise HTTPException(404, "That school code was not found")
    else:
        school = _self_study_school(db)
    u = User(role="student", name=body.name, school_id=school.id, board=body.board, cls=body.cls, lang=body.lang,
             pin_hash=hash_secret(body.pin))
    db.add(u)
    db.commit()
    return _token_out(u)


@router.post("/student/login", response_model=TokenOut)
def student_login(body: StudentLogin, db: Session = Depends(get_db)):
    u = db.get(User, body.student_id)
    generic = HTTPException(status.HTTP_401_UNAUTHORIZED, "That PIN does not match. Try again.")
    if not u or u.role != "student" or not u.pin_hash:
        raise generic
    now = clock.now()
    if u.locked_until:
        lu = u.locked_until if u.locked_until.tzinfo else u.locked_until.replace(tzinfo=now.tzinfo)
        if lu > now:
            mins = max(1, int((lu - now).total_seconds() // 60) + 1)
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"Too many wrong PINs. Try again in {mins} minutes.")
    if not verify_secret(body.pin, u.pin_hash):
        u.failed_pins += 1
        if u.failed_pins >= settings.pin_max_failures:
            u.locked_until = now + timedelta(minutes=settings.pin_lock_minutes)
            u.failed_pins = 0
        db.commit()
        raise generic
    u.failed_pins = 0
    u.locked_until = None
    db.commit()
    return _token_out(u)


@router.get("/demo-profiles")
def demo_profiles(db: Session = Depends(get_db)):
    """Names of the demo students, so a shared demo phone can show a profile picker. Off outside demo mode."""
    if not settings.seed_demo:
        return []
    rows = db.scalars(select(User).where(User.role == "student", User.is_sample.is_(False), User.pin_hash.is_not(None)).order_by(User.id).limit(10))
    return [{"id": u.id, "name": u.name, "cls": u.cls, "board": u.board} for u in rows]


@router.post("/otp/request")
def otp_request(body: OtpRequest, db: Session = Depends(get_db)):
    mobile = normalise_mobile(body.mobile)
    if len(mobile) != 10:
        raise HTTPException(422, "Enter a 10-digit mobile number")
    now = clock.now()
    hits = _otp_hits[mobile]
    while hits and (now - hits[0]).total_seconds() > 60:
        hits.popleft()
    if len(hits) >= settings.otp_requests_per_minute:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many code requests. Wait a minute.")
    hits.append(now)
    out: dict = {"sent": True, "expires_in": settings.otp_minutes * 60}
    user = db.scalar(select(User).where(User.mobile == mobile, User.role == body.role))
    if user:      # same response whether or not the number is registered
        code = make_otp()
        db.add(OtpCode(mobile=mobile, role=body.role, code_hash=hash_secret(code), expires_at=now + timedelta(minutes=settings.otp_minutes)))
        db.commit()
        if settings.demo_otp_visible:
            out["dev_code"] = code      # console SMS backend: demo only. Swap in a real SMS provider for production.
    return out


@router.post("/otp/verify", response_model=TokenOut)
def otp_verify(body: OtpVerify, db: Session = Depends(get_db)):
    mobile = normalise_mobile(body.mobile)
    now = clock.now()
    bad = HTTPException(status.HTTP_401_UNAUTHORIZED, "The mobile number or code does not match.")
    rec = db.scalar(select(OtpCode).where(OtpCode.mobile == mobile, OtpCode.role == body.role, OtpCode.used.is_(False))
                    .order_by(OtpCode.id.desc()))
    if not rec:
        raise bad
    exp = rec.expires_at if rec.expires_at.tzinfo else rec.expires_at.replace(tzinfo=now.tzinfo)
    if exp < now or rec.attempts >= settings.otp_max_attempts:
        raise bad
    if not verify_secret(body.code, rec.code_hash):
        rec.attempts += 1
        db.commit()
        raise bad
    rec.used = True
    user = db.scalar(select(User).where(User.mobile == mobile, User.role == body.role))
    db.commit()
    if not user:
        raise bad
    return _token_out(user)


@router.get("/me")
def me(user: User = Depends(current_user)):
    return public_user(user)
