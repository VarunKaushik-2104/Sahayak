"""Small admin commands.

    python -m app.cli check-content        validate the curriculum graph and questions
    python -m app.cli stats                how many schools, students, answers and messages are stored
    python -m app.cli feedback             print the messages sent through the contact form
    python -m app.cli purge-demo           delete sample/demo rows (the live site does this on start)
    python -m app.cli seed                 development only: create the demo school, users and sample class
"""
import sys

from .content import get_curriculum
from .db import SessionLocal, init_db
from .models import School, User


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
        elif cmd == "purge-demo":
            from .seed import purge_demo
            print("removed", purge_demo(db), "demo users")
        elif cmd == "stats":
            from sqlalchemy import func, select
            from .models import Attempt, Feedback
            n = lambda m, *w: db.scalar(select(func.count()).select_from(m).where(*w)) or 0
            print({"schools": n(School, School.code != "SELF"), "students": n(User, User.role == "student"), "teachers": n(User, User.role == "teacher"),
                   "parents": n(User, User.role == "parent"), "answers": n(Attempt), "messages": n(Feedback)})
        elif cmd == "feedback":
            from sqlalchemy import select
            from .models import Feedback
            for f in db.scalars(select(Feedback).order_by(Feedback.id.desc()).limit(50)):
                print(f"[{f.created_at:%Y-%m-%d %H:%M}] {f.name or '-'} <{f.email or '-'}>: {f.message}")
        else:
            print(__doc__); return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
