"""Real accounts: teacher and parent sign-up, school and family codes, deletion, contact form, demo purge."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app import clock
from app.models import Feedback, School, User
from app.seed import purge_demo

PW = "correct-horse-1"


def h(tok):
    return {"Authorization": "Bearer " + tok["access_token"]}


def new_teacher(client, school="Greenfield High", email="t1@example.com"):
    r = client.post("/api/auth/register-teacher", json={"name": "Mr. Rao", "email": email, "password": PW, "school_name": school})
    assert r.status_code == 201, r.text
    return r.json()


def new_student(client, code=None, name="Asha", board="TELANGANA", cls=8):
    r = client.post("/api/auth/register-student", json={"name": name, "pin": "4321", "board": board, "cls": cls, "school_code": code})
    assert r.status_code == 201, r.text
    return r.json()


def test_teacher_starts_a_school_and_a_joining_student_appears_on_the_heatmap(client):
    t = new_teacher(client)
    sch = client.get("/api/teacher/school", headers=h(t)).json()
    assert sch["name"] == "Greenfield High" and len(sch["code"]) == 6 and len(sch["staff_code"]) == 8 and sch["students"] == 0
    q = {"board": "TELANGANA", "cls": 8, "subject": "Maths"}
    assert client.get("/api/teacher/class", params=q, headers=h(t)).json()["empty"] is True      # a new school shows no invented students
    new_student(client, sch["code"].lower())                                                      # codes are not case sensitive
    rows = client.get("/api/teacher/class", params=q, headers=h(t)).json()["rows"]
    assert [r["name"] for r in rows] == ["Asha"] and rows[0]["sample"] is False
    assert client.get("/api/teacher/school", headers=h(t)).json()["students"] == 1


def test_self_study_students_are_invisible_to_teachers_until_they_join(client):
    t = new_teacher(client)
    s = new_student(client)                                  # no code
    q = {"board": "TELANGANA", "cls": 8, "subject": "Maths"}
    assert client.get("/api/teacher/class", params=q, headers=h(t)).json().get("empty") is True
    me = client.get("/api/student/me", headers=h(s)).json()
    assert me["school"] is None and len(me["link_code"]) == 6
    code = client.get("/api/teacher/school", headers=h(t)).json()["code"]
    assert client.post("/api/student/join-school", json={"code": "WRONG1"}, headers=h(s)).status_code == 404
    assert client.post("/api/student/join-school", json={"code": code}, headers=h(s)).status_code == 200
    assert [r["name"] for r in client.get("/api/teacher/class", params=q, headers=h(t)).json()["rows"]] == ["Asha"]
    assert client.get("/api/student/me", headers=h(s)).json()["school"]["name"] == "Greenfield High"
    assert client.delete("/api/student/school", headers=h(s)).status_code == 204
    assert client.get("/api/teacher/class", params=q, headers=h(t)).json().get("empty") is True


def test_colleague_joins_with_staff_code_and_teachers_never_cross_schools(client):
    a, b = new_teacher(client), new_teacher(client, "Other School", "t2@example.com")
    sa = client.get("/api/teacher/school", headers=h(a)).json()
    new_student(client, sa["code"])
    q = {"board": "TELANGANA", "cls": 8, "subject": "Maths"}
    assert client.get("/api/teacher/class", params=q, headers=h(b)).json().get("empty") is True
    r = client.post("/api/auth/register-teacher", json={"name": "Ms. Devi", "email": "t3@example.com", "password": PW, "staff_code": sa["staff_code"]})
    assert r.status_code == 201
    assert len(client.get("/api/teacher/class", params=q, headers=h(r.json())).json()["rows"]) == 1
    assert client.post("/api/auth/register-teacher", json={"name": "X", "email": "t4@example.com", "password": PW, "staff_code": sa["code"]}).status_code == 404   # the student code is not a staff code
    assert client.post("/api/auth/register-teacher", json={"name": "X", "email": "t5@example.com", "password": PW}).status_code == 422


def test_teacher_signup_validation_and_duplicates(client):
    new_teacher(client)
    base = {"name": "A", "email": "t1@example.com", "password": PW, "school_name": "S"}
    assert client.post("/api/auth/register-teacher", json=base).status_code == 409
    assert client.post("/api/auth/register-teacher", json=base | {"email": "T1@Example.com "}).status_code == 409      # case and spaces ignored
    assert client.post("/api/auth/register-teacher", json=base | {"email": "nope"}).status_code == 422
    assert client.post("/api/auth/register-teacher", json=base | {"email": "n@example.com", "password": "short"}).status_code == 422


def test_staff_login_lockout_and_no_account_enumeration(client):
    new_teacher(client)
    bad = lambda e, p="wrong-password": client.post("/api/auth/login", json={"email": e, "password": p, "role": "teacher"})
    unknown, wrong = bad("nobody@example.com"), bad("t1@example.com")
    assert unknown.status_code == wrong.status_code == 401 and unknown.json() == wrong.json()
    for _ in range(4):
        assert bad("t1@example.com").status_code == 401
    assert bad("t1@example.com", PW).status_code == 429                    # locked, even with the right password
    clock.set_now(datetime.now(timezone.utc) + timedelta(minutes=6))
    assert bad("t1@example.com", PW).status_code == 200
    assert client.post("/api/auth/login", json={"email": "t1@example.com", "password": PW, "role": "parent"}).status_code == 401   # role is checked


def test_parent_links_a_child_with_the_family_code_and_sees_only_that_child(client):
    t = new_teacher(client)
    code = client.get("/api/teacher/school", headers=h(t)).json()["code"]
    a, b = new_student(client, code, "Asha"), new_student(client, code, "Bala")
    fa = client.get("/api/student/me", headers=h(a)).json()
    assert client.post("/api/auth/register-parent", json={"name": "P", "email": "p@example.com", "password": PW, "link_code": "NOPE99"}).status_code == 404
    r = client.post("/api/auth/register-parent", json={"name": "Mrs. Rao", "email": "p@example.com", "password": PW, "link_code": fa["link_code"].lower()})
    assert r.status_code == 201
    p = h(r.json())
    assert [k["name"] for k in client.get("/api/parent/children", headers=p).json()] == ["Asha"]
    note = client.get("/api/parent/note", params={"student_id": a["user"]["id"]}, headers=p)
    assert note.status_code == 200 and "Bala" not in note.text
    assert client.get("/api/parent/note", params={"student_id": b["user"]["id"]}, headers=p).status_code == 403
    assert client.post("/api/auth/register-parent", json={"name": "P", "email": "p@example.com", "password": PW, "link_code": fa["link_code"]}).status_code == 409
    fb = client.get("/api/student/me", headers=h(b)).json()
    assert client.post("/api/parent/children", json={"code": fb["link_code"]}, headers=p).status_code == 201     # a second child
    assert len(client.get("/api/parent/children", headers=p).json()) == 2
    assert client.delete(f"/api/parent/children/{b['user']['id']}", headers=p).status_code == 204
    assert client.get("/api/student/me", headers=h(a)).json()["parents"] == 1


def test_student_can_remove_every_parent_and_the_old_code_stops_working(client):
    s = new_student(client)
    code = client.get("/api/student/me", headers=h(s)).json()["link_code"]
    p = h(client.post("/api/auth/register-parent", json={"name": "P", "email": "p@example.com", "password": PW, "link_code": code}).json())
    assert client.delete("/api/student/parents", headers=h(s)).status_code == 204
    assert client.get("/api/parent/children", headers=p).json() == []
    assert client.post("/api/parent/children", json={"code": code}, headers=p).status_code == 404
    rot = client.post("/api/student/link-code", headers=h(s)).json()["link_code"]
    assert rot != code and len(rot) == 6


def test_deleting_an_account_removes_the_students_data(client, db):
    s = new_student(client)
    uid = s["user"]["id"]
    assert client.delete("/api/auth/me", headers=h(s)).status_code == 204
    db.expire_all()
    assert db.get(User, uid) is None
    assert client.get("/api/student/me", headers=h(s)).status_code == 401


def test_teacher_can_delete_their_account_after_sending_practice(client):
    t = new_teacher(client)
    code = client.get("/api/teacher/school", headers=h(t)).json()["code"]
    new_student(client, code)
    assert client.post("/api/teacher/assign", json={"board": "TELANGANA", "cls": 8, "subject": "Maths", "group": "basics"}, headers=h(t)).status_code == 201
    assert client.delete("/api/auth/me", headers=h(t)).status_code == 204


def test_contact_form_stores_messages_and_stops_bots(client, db):
    ok = client.post("/api/feedback", json={"name": "Ravi", "email": "r@example.com", "message": "Please check chapter 3."})
    assert ok.status_code == 201
    client.post("/api/feedback", json={"message": "spam spam spam", "website": "http://bot"})        # honeypot: accepted silently, not stored
    msgs = db.scalars(select(Feedback)).all()
    assert [m.message for m in msgs] == ["Please check chapter 3."]
    assert client.post("/api/feedback", json={"message": "hi"}).status_code == 422
    codes = [client.post("/api/feedback", json={"message": "again and again"}).status_code for _ in range(6)]
    assert 429 in codes


def test_purge_demo_removes_sample_rows_and_keeps_real_users(client, db):
    real = new_student(client, "DEMO", "Real Kid")             # a real student who typed the old demo school code
    removed = purge_demo(db)
    assert removed > 30
    names = {u.name for u in db.scalars(select(User))}
    assert names == {"Real Kid"}
    assert db.scalar(select(School).where(School.code == "DEMO")) is not None      # school kept: a real user still belongs to it
    assert client.get("/api/student/me", headers=h(real)).status_code == 200


def test_a_profile_without_a_family_code_gets_one(client, db):
    s = new_student(client)
    u = db.get(User, s["user"]["id"])
    u.link_code = None
    db.commit()
    assert len(client.get("/api/student/me", headers=h(s)).json()["link_code"]) == 6
