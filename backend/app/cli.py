"""Small admin commands.

    python -m app.cli seed                 create/refresh the demo school, users and sample class
    python -m app.cli check-content        validate the curriculum graph and questions
    python -m app.cli add-teacher NAME MOBILE SCHOOL_CODE
    python -m app.cli add-parent NAME MOBILE STUDENT_ID
"""
import sys

from .content import get_curriculum
from .db import SessionLocal, init_db
from .models import ParentChild, School, User
from .security import normalise_mobile


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    cmd, args = argv[0], argv[1:]
    cur = get_curriculum()
    if cmd == "check-content":
        problems = cur.validate()
        print("OK" if not problems else "\n".join(problems), f"({len(cur.T)} topics, {cur.n_questions} questions)")
        return 1 if problems else 0
    init_db()
    with SessionLocal() as db:
        if cmd == "seed":
            from .seed import seed_demo
            print("created" if seed_demo(db, cur) else "refreshed")
        elif cmd == "add-teacher" and len(args) == 3:
            school = db.query(School).filter_by(code=args[2].upper()).first() or School(name=args[2], code=args[2].upper())
            db.add(school); db.flush()
            db.add(User(role="teacher", name=args[0], mobile=normalise_mobile(args[1]), school_id=school.id)); db.commit()
            print("teacher added")
        elif cmd == "add-parent" and len(args) == 3:
            kid = db.get(User, int(args[2]))
            if not kid or kid.role != "student":
                print("no such student"); return 1
            p = User(role="parent", name=args[0], mobile=normalise_mobile(args[1]), school_id=kid.school_id)
            db.add(p); db.flush(); db.add(ParentChild(parent_id=p.id, student_id=kid.id)); db.commit()
            print("parent added")
        else:
            print(__doc__); return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
