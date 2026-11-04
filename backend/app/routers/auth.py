"""Sign-in and sign-up.

Students: a profile and a 4-digit PIN (locks after repeated misses), optionally joined to a school with the school's code.
Teachers: email + password; the first teacher starts a school and gets its codes, colleagues join with the staff code.
Parents: email + password; they see only the child whose family code they enter.
Nothing is shown on screen as a "code sent to you": there is no SMS or email step to fake.
"""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import clock
from ..config import settings
from ..db import get_db
from ..deps import current_user
from ..models import Assignment, ParentChild, School, User
from ..schemas import RegisterParent, RegisterStudent, RegisterTeacher, StaffLogin, StudentLogin, TokenOut
from ..security import hash_secret, make_code, make_token, normalise_code, verify_secret

router = APIRouter(prefix="/auth", tags=["auth"])


def public_user(u: User) -> dict:
    d = {"id": u.id, "role": u.role, "name": u.name}
    if u.role == "student":
        d |= {"board": u.board, "cls": u.cls, "lang": u.lang, "subject": u.subject}
    return d


def _token_out(u: User) -> TokenOut:
    tok, ttl = make_token(u.id, u.role)
    return TokenOut(access_token=tok, expires_in=ttl, role=u.role, user=public_user(u))


def unique_code(db: Session, model, column, n: int) -> str:
    for _ in range(20):
        c = make_code(n)
        if not db.scalar(select(model).where(column == c)):
            return c
    raise HTTPException(500, "Could not make a code. Try again.")


def _self_study_school(db: Session) -> School:
    s = db.scalar(select(School).where(School.code == "SELF"))
    if not s:
        s = School(name="Self-study", code="SELF")
        db.add(s)
        db.flush()
    return s


def _check_lock(u: User) -> None:
    if not u.locked_until:
        return
    now = clock.now()
    lu = u.locked_until if u.locked_until.tzinfo else u.locked_until.replace(tzinfo=now.tzinfo)
    if lu > now:
        mins = max(1, int((lu - now).total_seconds() // 60) + 1)
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"Too many wrong attempts. Try again in {mins} {'minute' if mins == 1 else 'minutes'}.")


def _record_failure(db: Session, u: User, limit: int) -> None:
    u.failed_pins += 1
    if u.failed_pins >= limit:
        u.locked_until = clock.now() + timedelta(minutes=settings.pin_lock_minutes)
        u.failed_pins = 0
    db.commit()


def school_by_code(db: Session, raw: str) -> School:
    school = db.scalar(select(School).where(School.code == normalise_code(raw)))
    if not school or school.code == "SELF":
        raise HTTPException(404, "That school code was not found. Ask your teacher to check it.")
    return school


# ---- students ------------------------------------------------------------------------------
@router.post("/register-student", response_model=TokenOut, status_code=201)
def register_student(body: RegisterStudent, db: Session = Depends(get_db)):
    school = school_by_code(db, body.school_code) if (body.school_code or "").strip() else _self_study_school(db)
    u = User(role="student", name=body.name, school_id=school.id, board=body.board, cls=body.cls, lang=body.lang,
             pin_hash=hash_secret(body.pin), link_code=unique_code(db, User, User.link_code, 6))
    db.add(u)
    db.commit()
    return _token_out(u)


@router.post("/student/login", response_model=TokenOut)
def student_login(body: StudentLogin, db: Session = Depends(get_db)):
    u = db.get(User, body.student_id)
    generic = HTTPException(status.HTTP_401_UNAUTHORIZED, "That PIN does not match. Try again.")
    if not u or u.role != "student" or not u.pin_hash:
        raise generic
    _check_lock(u)
    if not verify_secret(body.pin, u.pin_hash):
        _record_failure(db, u, settings.pin_max_failures)
        raise generic
    u.failed_pins = 0
    u.locked_until = None
    db.commit()
    return _token_out(u)


@router.get("/demo-profiles")
def demo_profiles(db: Session = Depends(get_db)):
    """Names of the demo students, so a shared development phone can show a profile picker. Empty unless SEED_DEMO=1."""
    if not settings.seed_demo:
        return []
    rows = db.scalars(select(User).where(User.role == "student", User.is_sample.is_(False), User.pin_hash.is_not(None)).order_by(User.id).limit(10))
    return [{"id": u.id, "name": u.name, "cls": u.cls, "board": u.board} for u in rows]


# ---- teachers ------------------------------------------------------------------------------
@router.post("/register-teacher", response_model=TokenOut, status_code=201)
def register_teacher(body: RegisterTeacher, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == body.email, User.role == "teacher")):
        raise HTTPException(409, "A teacher account with this email already exists. Sign in instead.")
    if (body.staff_code or "").strip():
        school = db.scalar(select(School).where(School.staff_code == normalise_code(body.staff_code)))
        if not school:
            raise HTTPException(404, "That staff code was not found. Ask your colleague for the staff code on their dashboard.")
    else:
        if not (body.school_name or "").strip():
            raise HTTPException(422, "Enter your school's name, or a staff code from a colleague.")
        school = School(name=" ".join(body.school_name.split()), code=unique_code(db, School, School.code, 6),
                        staff_code=unique_code(db, School, School.staff_code, 8))
        db.add(school)
        db.flush()
    u = User(role="teacher", name=body.name, email=body.email, password_hash=hash_secret(body.password), school_id=school.id)
    db.add(u)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A teacher account with this email already exists. Sign in instead.")
    return _token_out(u)


# ---- parents -------------------------------------------------------------------------------
@router.post("/register-parent", response_model=TokenOut, status_code=201)
def register_parent(body: RegisterParent, db: Session = Depends(get_db)):
    kid = db.scalar(select(User).where(User.role == "student", User.link_code == normalise_code(body.link_code)))
    if not kid:
        raise HTTPException(404, "That family code was not found. Your child can see it on their Sahayak home screen.")
    if db.scalar(select(User).where(User.email == body.email, User.role == "parent")):
        raise HTTPException(409, "A parent account with this email already exists. Sign in, then add your child.")
    u = User(role="parent", name=body.name, email=body.email, password_hash=hash_secret(body.password), school_id=kid.school_id)
    db.add(u)
    try:
        db.flush()
        db.add(ParentChild(parent_id=u.id, student_id=kid.id))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A parent account with this email already exists. Sign in, then add your child.")
    return _token_out(u)


# ---- teacher and parent sign-in --------------------------------------------------------------
@router.post("/login", response_model=TokenOut)
def staff_login(body: StaffLogin, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == body.email, User.role == body.role))
    generic = HTTPException(status.HTTP_401_UNAUTHORIZED, "The email or password does not match.")
    if not u or not u.password_hash:
        verify_secret(body.password, "pbkdf2$1$AAAA$AAAA")       # spend similar time whether or not the email exists
        raise generic
    _check_lock(u)
    if not verify_secret(body.password, u.password_hash):
        _record_failure(db, u, settings.staff_max_failures)
        raise generic
    u.failed_pins = 0
    u.locked_until = None
    db.commit()
    return _token_out(u)


@router.get("/me")
def me(user: User = Depends(current_user)):
    return public_user(user)


@router.delete("/me", status_code=204)
def delete_me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Delete the signed-in account and everything attached to it (answers, mastery, links)."""
    if user.role == "teacher":
        db.execute(delete(Assignment).where(Assignment.created_by == user.id))
    db.delete(user)
    db.commit()
