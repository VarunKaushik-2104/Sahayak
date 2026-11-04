"""The teacher's class view: heatmap, groups, morning briefing, worksheets, the test the whole class prepares for."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import clock
from ..content import BOARDS, SUBJECTS, Curriculum
from ..db import get_db
from ..deps import curriculum, require_role
from ..engine import teacher as tch
from ..engine.mastery import get, mean
from ..models import Assignment, GroupOverride, School, TestPlan, User
from ..schemas import AssignIn, GroupIn, TestIn
from ..services import state

router = APIRouter(prefix="/teacher", tags=["teacher"])
Teacher = Depends(require_role("teacher"))


def _scope(board: str, cls: int, subject: str) -> None:
    if board not in BOARDS or subject not in SUBJECTS or not 6 <= cls <= 10:
        raise HTTPException(422, "Unknown board, class or subject")


def _short(name: str, n: int) -> str:
    return name if len(name) <= n else name[: n - 1] + "…"


@router.get("/school")
def school(user: User = Teacher, db: Session = Depends(get_db)):
    """The school this teacher belongs to, its two codes, and how many real students have joined."""
    sch = db.get(School, user.school_id)
    counts = db.execute(select(User.board, User.cls, func.count()).where(User.role == "student", User.school_id == sch.id, User.is_sample.is_(False))
                        .group_by(User.board, User.cls)).all()
    return {"name": sch.name, "code": sch.code, "staff_code": sch.staff_code,
            "students": sum(n for _, _, n in counts),
            "classes": [{"board": b, "cls": c, "students": n} for b, c, n in sorted(counts, key=lambda x: (x[0], x[1]))]}


@router.get("/class")
def class_view(board: str = Query(...), cls: int = Query(...), subject: str = Query(...),
               user: User = Teacher, db: Session = Depends(get_db), cur: Curriculum = Depends(curriculum)):
    _scope(board, cls, subject)
    today = clock.today()
    tp = state.get_or_create_test(db, cur, user.school_id, board, cls, subject)
    tv = state.test_view(cur, tp, today)
    rows = state.class_rows(db, cur, user.school_id, board, cls)
    groups = state.group_map(db, cur, user.school_id, rows, tv["topics"])
    db.commit()
    ts = tv["topics"]
    pre_all = [t for t in cur.closure_of(ts) if t not in ts]
    chs = cur.chapters(board, cls, subject)

    topic_ids = list(dict.fromkeys([*ts, *pre_all[:4]]))
    topic_cols = [{"id": t, "label": ("C%d " % cur.T[t]["cls"] if cur.T[t]["cls"] != cls else "") + _short(cur.T[t]["name"], 15)} for t in topic_ids]
    chap_cols = [{"label": _short(c["name"], 16), "chapter": c["name"]} for c in chs] + [{"label": "Test ready", "chapter": None}]

    def chapter_cells(P):
        return [round(mean(get(P, t) for t in c["topics"]), 3) for c in chs] + [round(mean(get(P, t) for t in ts), 3)]

    out_rows = [{"id": r.id, "name": r.name, "sample": r.sample, "last_sync": r.last_sync, "stale": r.stale, "group": groups[r.id],
                 "topic_cells": [round(get(r.P, t), 3) for t in topic_ids], "chapter_cells": chapter_cells(r.P),
                 "test_ready": round(mean(get(r.P, t) for t in ts), 3)} for r in rows]
    if not rows:
        return {"scope": {"board": board, "cls": cls, "subject": subject}, "test": state.public_test(tv), "rows": [], "empty": True}
    return {
        "scope": {"board": board, "cls": cls, "subject": subject},
        "test": state.public_test(tv),
        "rows": out_rows, "topic_columns": topic_cols, "chapter_columns": chap_cols,
        "groups": {k: {**v, "students": [r.id for r in rows if groups[r.id] == k]} for k, v in tch.GROUPS.items()},
        "briefing": tch.briefing(cur, rows, {"name": tv["name"], "date": tv["date"], "topics": ts}, groups, today),
        "worksheets": tch.worksheets(cur, rows, {"topics": ts}, groups),
        "after_test": tch.after_test(cur, rows, tv["chapter_objs"]),
        "latest_mocks": _latest_mocks(db, [r.id for r in rows if not r.sample], subject),
        "server_time": clock.now().isoformat(),
    }


def _latest_mocks(db: Session, ids: list[int], subject: str) -> list[dict]:
    from sqlalchemy import select

    from ..models import MockResult
    out = []
    for sid in ids:
        m = db.scalar(select(MockResult).where(MockResult.student_id == sid, MockResult.subject == subject).order_by(MockResult.id.desc()))
        if m:
            out.append({"student_id": sid, "name": db.get(User, sid).name, "score": m.score, "total": m.total})
    return out


@router.put("/test")
def set_test(body: TestIn, user: User = Teacher, db: Session = Depends(get_db), cur: Curriculum = Depends(curriculum)):
    today = clock.today()
    if not 1 <= (body.date - today).days <= 90:
        raise HTTPException(422, "The test date must be between tomorrow and 90 days away")
    allch = [c["name"] for c in cur.chapters(body.board, body.cls, body.subject)]
    unknown = [c for c in body.chapters if c not in allch]
    if unknown:
        raise HTTPException(422, f"Not chapters of this class and subject: {', '.join(unknown)}")
    tp = state.get_or_create_test(db, cur, user.school_id, body.board, body.cls, body.subject)
    tp.name, tp.test_date = body.name.strip(), body.date
    tp.chapters = [c for c in allch if c in set(body.chapters)]
    db.commit()
    return state.public_test(state.test_view(cur, tp, today))


@router.put("/group")
def move_student(body: GroupIn, user: User = Teacher, db: Session = Depends(get_db)):
    s = db.get(User, body.student_id)
    if not s or s.role != "student" or s.school_id != user.school_id:
        raise HTTPException(404, "No such student in your school")
    row = db.get(GroupOverride, (user.school_id, s.id))
    if row:
        row.group = body.group
    else:
        db.add(GroupOverride(teacher_school_id=user.school_id, student_id=s.id, group=body.group))
    db.commit()
    return {"student_id": s.id, "group": body.group}


@router.post("/assign", status_code=201)
def assign(body: AssignIn, user: User = Teacher, db: Session = Depends(get_db), cur: Curriculum = Depends(curriculum)):
    _scope(body.board, body.cls, body.subject)
    a = Assignment(school_id=user.school_id, board=body.board, cls=body.cls, subject=body.subject, group=body.group,
                   text=tch.GROUPS[body.group]["homework"], created_by=user.id)
    db.add(a)
    db.commit()
    return {"id": a.id, "group": a.group, "text": a.text}
