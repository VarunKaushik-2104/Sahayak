"""Development data only: one school, a teacher, a parent, a student (Ravi) and sample classmates for every board and class.

Used by the test-suite and by `SEED_DEMO=1` on a developer's machine. The live site never runs it: with SEED_DEMO off,
`purge_demo` removes anything this file created, so the deployed database holds only data entered by real users.
Sample classmates have no login; their mastery comes from a generator, which is why they must never reach production.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import clock
from .content import BOARDS, Curriculum
from .engine.seedgen import seed_mastery
from .models import Mastery, ParentChild, School, TestPlan, User
from .security import hash_secret

DEMO_TEACHER_EMAIL = "teacher@demo.sahayak.local"
DEMO_PARENT_EMAIL = "parent@demo.sahayak.local"
DEMO_PASSWORD = "demo-password-1"
DEMO_RAVI_PIN = "1234"
DEMO_DOMAIN = "@demo.sahayak.local"
ROSTER = [("Ananya R.", "strong"), ("Imran S.", "gap"), ("Sneha P.", "avg"), ("Karthik N.", "weak"),
          ("Fatima B.", "strong"), ("Harsh V.", "gap"), ("Divya R.", "avg")]


def _put_mastery(db: Session, uid: int, P: dict[str, float]) -> None:
    db.add_all(Mastery(student_id=uid, topic=t, p=p) for t, p in P.items())


def seed_demo(db: Session, cur: Curriculum) -> bool:
    """Returns True if the demo data was created now, False if it already existed (it is then only refreshed)."""
    now = clock.now()
    school = db.scalar(select(School).where(School.code == "DEMO"))
    created = school is None
    if created:
        school = School(name="Sahayak Demo School", code="DEMO", staff_code="DEMOSTAFF")
        db.add(school)
        db.flush()
        teacher = User(role="teacher", name="Ms. Lakshmi", school_id=school.id, email=DEMO_TEACHER_EMAIL, password_hash=hash_secret(DEMO_PASSWORD))
        ravi = User(role="student", name="Ravi K.", school_id=school.id, board="TELANGANA", cls=8, lang="en",
                    pin_hash=hash_secret(DEMO_RAVI_PIN), link_code="DEMO22", last_sync_at=now - timedelta(days=2, hours=1))
        parent = User(role="parent", name="Parent of Ravi K.", school_id=school.id, email=DEMO_PARENT_EMAIL, password_hash=hash_secret(DEMO_PASSWORD))
        db.add_all([teacher, ravi, parent])
        db.flush()
        db.add(ParentChild(parent_id=parent.id, student_id=ravi.id))
        _put_mastery(db, ravi.id, {**seed_mastery(cur, 8, "Maths", "gap", 11), **seed_mastery(cur, 8, "Science", "gap", 12)})
        for b in BOARDS:
            for c in (6, 7, 8, 9, 10):
                base = c * 17 + (BOARDS.index(b) + 1) * 131
                for i, (name, arch) in enumerate(ROSTER):
                    stale = {3: timedelta(days=2, hours=1), 5: timedelta(days=3)}.get(i)
                    u = User(role="student", name=name, school_id=school.id, board=b, cls=c, lang="en", is_sample=True,
                             last_sync_at=now - (stale or timedelta(hours=1 + i)))
                    db.add(u)
                    db.flush()
                    _put_mastery(db, u.id, {**seed_mastery(cur, c, "Maths", arch, base + 1 + i * 7),
                                            **seed_mastery(cur, c, "Science", arch, base + 2 + i * 7)})
    else:   # refresh: keep the sample class looking current, and move past tests forward
        for u in db.scalars(select(User).where(User.school_id == school.id, User.is_sample.is_(True))):
            i = [n for n, _ in ROSTER].index(u.name)
            if i not in (3, 5):
                u.last_sync_at = now - timedelta(hours=1 + i)
        for tp in db.scalars(select(TestPlan).where(TestPlan.school_id == school.id)):
            if tp.test_date <= clock.today():
                tp.test_date = clock.today() + timedelta(days=6)
    db.commit()
    return created


def purge_demo(db: Session) -> int:
    """Delete every row the demo seed made (sample students, demo teacher, parent and Ravi). Real users are never touched."""
    from sqlalchemy import delete, inspect, text

    from .models import Assignment

    school = db.scalar(select(School).where(School.code == "DEMO"))
    ids = set(db.scalars(select(User.id).where(User.is_sample.is_(True))))
    ids |= set(db.scalars(select(User.id).where(User.email.like(f"%{DEMO_DOMAIN}"))))
    if school:
        ids |= set(db.scalars(select(User.id).where(User.school_id == school.id, User.name == "Ravi K.", User.role == "student",
                                                    User.is_sample.is_(False))))
    if "mobile" in {c["name"] for c in inspect(db.get_bind()).get_columns("users")}:     # accounts from the first release
        ids |= {r[0] for r in db.execute(text("SELECT id FROM users WHERE mobile IN ('9000000002','9000000003')"))}
    if ids:
        db.execute(delete(Assignment).where(Assignment.created_by.in_(ids)))
        db.execute(delete(User).where(User.id.in_(ids)))
    if school and not db.scalar(select(User.id).where(User.school_id == school.id)):
        for tp in db.scalars(select(TestPlan).where(TestPlan.school_id == school.id)):
            db.delete(tp)
        db.delete(school)
    db.commit()
    return len(ids)
