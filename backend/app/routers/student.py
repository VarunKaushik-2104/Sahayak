"""Everything a student's phone needs, and nothing about anyone else."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .. import clock
from ..content import SUBJECTS, Curriculum
from ..db import get_db
from ..deps import curriculum, require_role
from ..engine import mock as mock_engine
from ..engine.planner import build_plan, chapter_mastery, readiness
from ..models import Assignment, MockResult, ParentChild, School, User
from ..schemas import CodeIn, MockSubmit, ProfilePatch, SyncEvent, SyncIn
from ..services import state
from .auth import _self_study_school, school_by_code, unique_code
from ..services.sync import apply_events

router = APIRouter(tags=["student"])
Student = Depends(require_role("student"))


@router.get("/student/me")
def me(user: User = Student, db: Session = Depends(get_db), cur: Curriculum = Depends(curriculum)):
    today = clock.today()
    P = state.load_P(db, user.id)
    tests, groups = {}, {}
    for s in SUBJECTS:
        tp = state.get_or_create_test(db, cur, user.school_id, user.board, user.cls, s)
        tv = state.test_view(cur, tp, today)
        tests[s] = state.public_test(tv)
        groups[s] = state.student_group(db, cur, user, tv)
    if not user.link_code:      # profiles made before family codes existed get one on next sign-in
        user.link_code = unique_code(db, User, User.link_code, 6)
    db.commit()
    # the newest practice a teacher sent to this student's group
    asg = None
    for s in SUBJECTS:
        a = db.scalar(select(Assignment).where(Assignment.school_id == user.school_id, Assignment.board == user.board,
                                               Assignment.cls == user.cls, Assignment.subject == s, Assignment.group == groups[s])
                      .order_by(Assignment.id.desc()))
        if a and (asg is None or a.id > asg[0].id):
            asg = (a, s)
    last_mock = db.scalar(select(MockResult).where(MockResult.student_id == user.id).order_by(MockResult.id.desc()))
    return {
        "id": user.id, "name": user.name, "board": user.board, "cls": user.cls, "lang": user.lang, "subject": user.subject,
        "P": P, "misc": state.load_misc(db, user.id), "minutes": state.minutes_by_day(db, user.id, today),
        "tests": tests, "groups": groups,
        "assignment": {"text": asg[0].text, "subject": asg[1], "sent": asg[0].created_at.isoformat()} if asg else None,
        "last_mock": {"score": last_mock.score, "total": last_mock.total, "name": last_mock.name, "subject": last_mock.subject,
                      "when": last_mock.taken_at.isoformat()} if last_mock else None,
        "content_version": cur.version, "server_time": clock.now().isoformat(),
        "school": _school_info(db, user), "link_code": user.link_code,
        "parents": db.scalar(select(func.count()).select_from(ParentChild).where(ParentChild.student_id == user.id)) or 0,
    }


def _school_info(db: Session, user: User) -> dict | None:
    sch = db.get(School, user.school_id) if user.school_id else None
    return None if sch is None or sch.code == "SELF" else {"name": sch.name, "code": sch.code}


@router.post("/student/join-school")
def join_school(body: CodeIn, user: User = Student, db: Session = Depends(get_db)):
    """Join a school after signing up. The student then appears on that school's teacher dashboard."""
    sch = school_by_code(db, body.code)
    user.school_id = sch.id
    db.commit()
    return {"school": {"name": sch.name, "code": sch.code}}


@router.delete("/student/school", status_code=204)
def leave_school(user: User = Student, db: Session = Depends(get_db)):
    user.school_id = _self_study_school(db).id
    db.commit()


@router.post("/student/link-code")
def new_link_code(user: User = Student, db: Session = Depends(get_db)):
    """A new family code. Parents already linked stay linked; only new sign-ups need the new code."""
    user.link_code = unique_code(db, User, User.link_code, 6)
    db.commit()
    return {"link_code": user.link_code}


@router.delete("/student/parents", status_code=204)
def unlink_parents(user: User = Student, db: Session = Depends(get_db)):
    """The student removes every parent's access."""
    db.execute(delete(ParentChild).where(ParentChild.student_id == user.id))
    user.link_code = unique_code(db, User, User.link_code, 6)
    db.commit()


@router.patch("/student/me")
def patch_me(body: ProfilePatch, user: User = Student, db: Session = Depends(get_db)):
    if body.lang:
        user.lang = body.lang
    if body.subject:
        user.subject = body.subject
    db.commit()
    return {"lang": user.lang, "subject": user.subject}


@router.get("/student/plan")
def plan(subject: str = Query("Maths"), term_date: date | None = None, user: User = Student,
         db: Session = Depends(get_db), cur: Curriculum = Depends(curriculum)):
    """Revision plan to the teacher's test, or to a half-yearly exam date the student picks."""
    if subject not in SUBJECTS:
        raise HTTPException(422, "Unknown subject")
    today = clock.today()
    P = state.load_P(db, user.id)
    if term_date:
        if not 1 <= (term_date - today).days <= 90:
            raise HTTPException(422, "Pick a date between tomorrow and 90 days away")
        chs, test_date, name = cur.chapters(user.board, user.cls, subject), term_date, "Half-yearly exam"
    else:
        tv = state.test_view(cur, state.get_or_create_test(db, cur, user.school_id, user.board, user.cls, subject), today)
        chs, test_date, name = tv["chapter_objs"], date.fromisoformat(tv["date"]), tv["name"]
    out = build_plan(cur, P, chs, test_date, today)
    out |= {"exam": name, "date": test_date.isoformat(), "readiness": round(readiness(cur, P, chs), 3),
            "chapters": [{"name": c["name"], "mastery": round(chapter_mastery(P, c), 3)} for c in chs]}
    return out


@router.get("/student/mock")
def build_mock(subject: str = Query("Maths"), user: User = Student, db: Session = Depends(get_db), cur: Curriculum = Depends(curriculum)):
    """A mock paper for the current test. Options only: the key stays on the server."""
    if subject not in SUBJECTS:
        raise HTTPException(422, "Unknown subject")
    tv = state.test_view(cur, state.get_or_create_test(db, cur, user.school_id, user.board, user.cls, subject), clock.today())
    items = mock_engine.build_mock(cur, state.load_P(db, user.id), tv["chapter_objs"], subject)
    return {"name": tv["name"], "items": [mock_engine.public_item(cur, i) for i in items]}


@router.post("/student/mock/submit")
def submit_mock(body: MockSubmit, user: User = Student, db: Session = Depends(get_db), cur: Curriculum = Depends(curriculum)):
    ev = SyncEvent(cid=body.cid, type="mock", ts=clock.now(), name=body.name, subject=body.subject, rows=body.rows, minutes=body.minutes)
    rep, P = apply_events(db, cur, user, [ev])
    if rep.rejected:
        db.rollback()
        raise HTTPException(422, rep.rejected[0]["reason"])
    db.commit()
    res = db.scalar(select(MockResult).where(MockResult.student_id == user.id, MockResult.cid == body.cid))
    return {"score": res.score, "total": res.total, "rows": res.detail, "duplicate": bool(rep.duplicates)}


@router.post("/sync")
def sync(body: SyncIn, user: User = Student, db: Session = Depends(get_db), cur: Curriculum = Depends(curriculum)):
    """Offline outbox in, authoritative state out. Safe to retry."""
    rep, P = apply_events(db, cur, user, body.events)
    db.commit()
    return {"accepted": rep.accepted, "duplicates": rep.duplicates, "rejected": rep.rejected,
            "P": P, "misc": state.load_misc(db, user.id), "minutes": state.minutes_by_day(db, user.id, clock.today()),
            "server_time": clock.now().isoformat()}
