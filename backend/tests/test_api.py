from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app import clock
from app.models import Attempt, User
from conftest import login_staff, login_student

T = "m8_alg"


def qa(cur, topic=T, i=0, right=True):
    q = cur.T[topic]["qs"][i]
    o = next(o for o in q["o"] if bool(o.get("ok")) == right)
    return q["id"], o["t"]


def ev(cid, qid, pick, ts=None, kind="practice"):
    return {"cid": cid, "type": "answer", "kind": kind, "qid": qid, "pick": pick,
            "ts": (ts or datetime.now(timezone.utc)).isoformat()}


# ---------------- health, content ----------------
def test_health_and_content(client, cur):
    h = client.get("/api/health").json()
    assert h["status"] == "ok" and h["topics"] == 73
    r = client.get("/api/content/bundle")
    assert r.status_code == 200 and r.headers["etag"]
    assert client.get("/api/content/bundle", headers={"If-None-Match": r.headers["etag"]}).status_code == 304
    assert len(client.get("/api/content/chapters", params={"board": "CBSE", "cls": 8, "subject": "Maths"}).json()) > 3
    assert client.get("/api/content/chapters", params={"board": "XX", "cls": 8, "subject": "Maths"}).status_code == 422
    assert client.get("/api/content/topics/nope").status_code == 404


# ---------------- auth ----------------
def test_student_login_and_wrong_pin_lockout(client):
    sid = client.get("/api/auth/demo-profiles").json()[0]["id"]
    for _ in range(4):
        assert client.post("/api/auth/student/login", json={"student_id": sid, "pin": "0000"}).status_code == 401
    assert client.post("/api/auth/student/login", json={"student_id": sid, "pin": "0000"}).status_code == 401   # 5th miss locks
    r = client.post("/api/auth/student/login", json={"student_id": sid, "pin": "1234"})
    assert r.status_code == 429                                                  # even the right PIN is refused while locked
    clock.set_now(datetime.now(timezone.utc) + timedelta(minutes=6))
    assert client.post("/api/auth/student/login", json={"student_id": sid, "pin": "1234"}).status_code == 200


def test_register_student_validates_and_signs_in(client):
    bad = {"name": "Asha", "pin": "12", "board": "CBSE", "cls": 7}
    assert client.post("/api/auth/register-student", json=bad).status_code == 422
    assert client.post("/api/auth/register-student", json=bad | {"pin": "4321", "cls": 11}).status_code == 422
    r = client.post("/api/auth/register-student", json=bad | {"pin": "4321"})
    assert r.status_code == 201 and r.json()["role"] == "student"
    h = {"Authorization": "Bearer " + r.json()["access_token"]}
    me = client.get("/api/student/me", headers=h).json()
    assert me["name"] == "Asha" and me["P"] == {} and me["board"] == "CBSE"


def test_register_unknown_school_code(client):
    r = client.post("/api/auth/register-student", json={"name": "A", "pin": "1111", "board": "CBSE", "cls": 6, "school_code": "NOPE"})
    assert r.status_code == 404


def test_tokens_expire_and_garbage_is_rejected(client):
    h = login_student(client)
    assert client.get("/api/student/me", headers=h).status_code == 200
    assert client.get("/api/student/me", headers={"Authorization": "Bearer abc"}).status_code == 401
    assert client.get("/api/student/me").status_code == 401
    clock.set_now(datetime.now(timezone.utc) + timedelta(days=31))
    assert client.get("/api/student/me", headers=h).status_code == 401


def test_roles_are_separated(client):
    s, t, p = login_student(client), login_staff(client, "teacher"), login_staff(client, "parent")
    q = {"board": "TELANGANA", "cls": 8, "subject": "Maths"}
    assert client.get("/api/teacher/class", params=q, headers=s).status_code == 403
    assert client.get("/api/teacher/class", params=q, headers=p).status_code == 403
    assert client.get("/api/student/me", headers=t).status_code == 403
    assert client.get("/api/parent/children", headers=s).status_code == 403
    assert client.post("/api/sync", json={"events": []}, headers=t).status_code == 403


# ---------------- student, sync ----------------
def test_student_me_has_state_tests_and_groups(client):
    me = client.get("/api/student/me", headers=login_student(client)).json()
    assert me["name"] == "Ravi K." and len(me["P"]) > 10 and me["P"]["m8_alg"] < 0.8
    assert set(me["tests"]) == {"Maths", "Science"} and me["tests"]["Maths"]["days"] == 6
    assert me["groups"]["Maths"] in ("extend", "practise", "basics")


def test_sync_marks_on_the_server_and_updates_mastery(client, cur):
    h = login_student(client)
    before = client.get("/api/student/me", headers=h).json()["P"][T]
    qid, right = qa(cur)
    r = client.post("/api/sync", json={"events": [ev("c-000001", qid, right)]}, headers=h).json()
    assert r["accepted"] == 1 and r["P"][T] > before


def test_a_forged_claim_changes_nothing(client, cur):
    """The phone sends what was picked. A client cannot say 'I was right': the server checks the curriculum."""
    h = login_student(client)
    qid, wrong = qa(cur, right=False)
    before = client.get("/api/student/me", headers=h).json()["P"][T]
    body = {"events": [{**ev("c-000002", qid, wrong), "ok": True, "mastery": 0.99}]}
    r = client.post("/api/sync", json=body, headers=h).json()
    assert r["P"][T] < before
    bad = client.post("/api/sync", json={"events": [ev("c-000003", qid, "made-up answer"), ev("c-000004", "zzz_1", "x")]}, headers=h).json()
    assert bad["accepted"] == 0 and len(bad["rejected"]) == 2 and bad["P"][T] == r["P"][T]


def test_sync_is_idempotent(client, cur):
    h = login_student(client)
    qid, right = qa(cur)
    body = {"events": [ev("c-000005", qid, right)]}
    a = client.post("/api/sync", json=body, headers=h).json()
    b = client.post("/api/sync", json=body, headers=h).json()
    assert a["accepted"] == 1 and b["accepted"] == 0 and b["duplicates"] == 1 and a["P"][T] == b["P"][T]


def test_events_apply_in_time_order_and_future_clocks_are_clamped(client, cur, db):
    h = login_student(client)
    qid, right = qa(cur, i=0)
    qid2, wrong = qa(cur, i=1, right=False)
    t0 = datetime.now(timezone.utc) - timedelta(hours=3)
    events = [ev("c-000007", qid2, wrong, t0 + timedelta(minutes=5)), ev("c-000006", qid, right, t0),
              ev("c-000008", qid, right, datetime.now(timezone.utc) + timedelta(days=400))]
    r = client.post("/api/sync", json={"events": events}, headers=h).json()
    assert r["accepted"] == 3
    rows = db.scalars(select(Attempt).order_by(Attempt.id)).all()
    assert [a.cid for a in rows[:2]] == ["c-000006", "c-000007"]
    assert all(a.answered_at.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc) for a in rows)


def test_sync_is_limited_to_the_signed_in_student(client, cur, db):
    h = login_student(client)
    qid, right = qa(cur)
    client.post("/api/sync", json={"events": [ev("c-000009", qid, right)]}, headers=h)
    other = client.post("/api/auth/register-student", json={"name": "Zed", "pin": "9999", "board": "CBSE", "cls": 8}).json()
    h2 = {"Authorization": "Bearer " + other["access_token"]}
    assert client.get("/api/student/me", headers=h2).json()["P"] == {}


def test_placement_event_sets_a_starting_picture_and_spreads(client, cur):
    h = login_student(client, None)
    reg = client.post("/api/auth/register-student", json={"name": "New", "pin": "2222", "board": "TELANGANA", "cls": 8}).json()
    h = {"Authorization": "Bearer " + reg["access_token"]}
    ans = []
    for t in ("m6_num", "m7_lin", "m6_ratio"):
        if t in cur.T:
            q = next(q for q in cur.T[t]["qs"] if q["lvl"] == 2)
            ans.append({"qid": q["id"], "pick": next(o["t"] for o in q["o"] if o.get("ok"))})
    r = client.post("/api/sync", json={"events": [{"cid": "place-0001", "type": "placement", "ts": datetime.now(timezone.utc).isoformat(), "answers": ans}]}, headers=h).json()
    assert r["accepted"] == 1 and len(r["P"]) >= len(ans)
    assert all(v > 0.5 for k, v in r["P"].items() if k in {a["qid"].rsplit("_", 1)[0] for a in ans})
    again = client.post("/api/sync", json={"events": [{"cid": "place-0001", "type": "placement", "ts": datetime.now(timezone.utc).isoformat(), "answers": ans}]}, headers=h).json()
    assert again["duplicates"] == 1 and again["P"] == r["P"]


def test_mock_build_hides_key_and_submit_marks_by_step(client, cur):
    h = login_student(client)
    paper = client.get("/api/student/mock", params={"subject": "Maths"}, headers=h).json()
    assert "ok" not in str(paper) and paper["items"][-1]["kind"] == "steps"
    rows = []
    for it in paper["items"]:
        if it["kind"] == "mcq":
            q = cur.question(it["qid"])[1]
            rows.append({"kind": "mcq", "qid": it["qid"], "pick": next(o["t"] for o in q["o"] if o.get("ok"))})
        else:
            parts = cur.T[it["topic"]]["steps"]["parts"]
            picks = [next(o["t"] for o in p["o"] if o.get("ok")) for p in parts]
            picks[-1] = next(o["t"] for o in parts[-1]["o"] if not o.get("ok"))
            rows.append({"kind": "steps", "topic": it["topic"], "picks": picks})
    res = client.post("/api/student/mock/submit", json={"cid": "mock-0001", "subject": "Maths", "rows": rows, "minutes": 12}, headers=h).json()
    assert res["total"] == 7 and res["score"] == 6
    assert client.post("/api/student/mock/submit", json={"cid": "mock-0001", "subject": "Maths", "rows": rows}, headers=h).json()["duplicate"]
    assert client.get("/api/student/me", headers=h).json()["last_mock"]["score"] == 6
    bad = client.post("/api/student/mock/submit", json={"cid": "mock-0002", "subject": "Maths", "rows": [{"kind": "mcq", "qid": "x_1", "pick": "y"}]}, headers=h)
    assert bad.status_code == 422


def test_plan_to_teacher_test_and_to_a_term_date(client):
    h = login_student(client)
    p = client.get("/api/student/plan", params={"subject": "Maths"}, headers=h).json()
    assert p["days"] == 6 and p["items"][-1]["kind"] == "mock"
    kinds = [i["kind"] for i in p["items"][:-1]]
    assert kinds == sorted(kinds, key=lambda k: k != "catchup")
    far = (clock.today() + timedelta(days=30)).isoformat()
    t = client.get("/api/student/plan", params={"subject": "Maths", "term_date": far}, headers=h).json()
    assert t["exam"] == "Half-yearly exam" and len(t["items"]) == 14
    assert client.get("/api/student/plan", params={"term_date": (clock.today() - timedelta(days=1)).isoformat()}, headers=h).status_code == 422


# ---------------- online practice ----------------
def test_online_practice_traces_back_and_is_idempotent(client, cur):
    h = login_student(client)
    nxt = client.post("/api/practice/next", json={"target": "m8_alg"}, headers=h).json()
    assert nxt["phase"] == "solve" and "ok" not in str(nxt) and len(nxt["question"]["options"]) >= 3
    traced = None
    for tid in cur.T:
        if tid.startswith("m8"):
            for q in cur.T[tid]["qs"]:
                for o in q["o"]:
                    if o.get("g"):
                        traced = (tid, q, o)
                        break
                if traced: break
        if traced: break
    tid, q, o = traced
    body = {"cid": "prac-0001", "qid": q["id"], "pick": o["t"], "target": tid}
    me = client.get("/api/student/me", headers=h).json()["P"]
    r = client.post("/api/practice/answer", json=body, headers=h).json()
    assert r["ok"] is False and r["misconception"] and r["mastery"] < r["mastery_before"]
    if me.get(o["g"], 0.5) < 0.75:
        assert r["trace_to"]["topic"] == o["g"] and r["focus"] == o["g"]
    again = client.post("/api/practice/answer", json=body, headers=h).json()
    assert again["duplicate"] is True
    assert client.post("/api/practice/answer", json={**body, "cid": "prac-0002", "pick": "nope"}, headers=h).status_code == 422
    assert client.post("/api/practice/next", json={"target": "bad"}, headers=h).status_code == 422


# ---------------- teacher ----------------
Q = {"board": "TELANGANA", "cls": 8, "subject": "Maths"}


def test_teacher_dashboard(client):
    t = login_staff(client, "teacher")
    d = client.get("/api/teacher/class", params=Q, headers=t).json()
    names = [r["name"] for r in d["rows"]]
    assert names[-1] != "Ravi K." and "Ravi K." in names and len(names) == 8
    assert len(d["briefing"]["items"]) == 5 and d["briefing"]["stale"] >= 2
    assert {r["group"] for r in d["rows"]} <= {"extend", "practise", "basics"}
    assert [w["level"] for w in d["worksheets"]] == [1, 2, 3]
    ravi = next(r for r in d["rows"] if r["name"] == "Ravi K.")
    assert ravi["stale"] is True and len(ravi["topic_cells"]) == len(d["topic_columns"])
    assert d["chapter_columns"][-1]["label"] == "Test ready" and len(d["after_test"]) >= 1


def test_syncing_clears_the_stale_flag_and_moves_the_row(client, cur):
    t = login_staff(client, "teacher")
    s = login_student(client)
    row = lambda: next(r for r in client.get("/api/teacher/class", params=Q, headers=t).json()["rows"] if r["name"] == "Ravi K.")
    assert row()["stale"]
    qid, right = qa(cur)
    client.post("/api/sync", json={"events": [ev("c-000020", qid, right)]}, headers=s)
    assert row()["stale"] is False


def test_teacher_sets_test_and_everyone_follows(client):
    t = login_staff(client, "teacher")
    s, p = login_student(client), login_staff(client, "parent")
    chs = client.get("/api/content/chapters", params=Q, headers=t).json()
    new = (clock.today() + timedelta(days=3)).isoformat()
    r = client.put("/api/teacher/test", json={**Q, "name": "Weekly Test", "date": new, "chapters": [chs[3]["name"]]}, headers=t)
    assert r.status_code == 200 and r.json()["days"] == 3
    me = client.get("/api/student/me", headers=s).json()
    assert me["tests"]["Maths"]["name"] == "Weekly Test" and me["tests"]["Maths"]["days"] == 3
    kid = client.get("/api/parent/children", headers=p).json()[0]["id"]
    note = client.get("/api/parent/note", params={"student_id": kid}, headers=p).json()
    assert "Weekly Test" in note["text"] and "in 3 days" in note["text"]
    assert client.put("/api/teacher/test", json={**Q, "date": new, "chapters": ["Not a chapter"]}, headers=t).status_code == 422
    assert client.put("/api/teacher/test", json={**Q, "date": (clock.today() - timedelta(days=1)).isoformat(), "chapters": [chs[0]["name"]]}, headers=t).status_code == 422


def test_teacher_moves_a_student_and_sends_practice(client):
    t = login_staff(client, "teacher")
    s = login_student(client)
    d = client.get("/api/teacher/class", params=Q, headers=t).json()
    ravi = next(r for r in d["rows"] if r["name"] == "Ravi K.")
    assert client.put("/api/teacher/group", json={"student_id": ravi["id"], "group": "extend"}, headers=t).status_code == 200
    assert client.get("/api/student/me", headers=s).json()["groups"]["Maths"] == "extend"
    assert client.post("/api/teacher/assign", json={**Q, "group": "extend"}, headers=t).status_code == 201
    a = client.get("/api/student/me", headers=s).json()["assignment"]
    assert a and "Challenge" in a["text"]
    assert client.put("/api/teacher/group", json={"student_id": 99999, "group": "extend"}, headers=t).status_code == 404


def test_teacher_cannot_touch_another_school(client, db):
    from app.models import School
    other = School(name="Other", code="OTH")
    db.add(other); db.flush()
    stranger = User(role="student", name="Out", school_id=other.id, board="TELANGANA", cls=8, is_sample=True)
    db.add(stranger); db.commit()
    t = login_staff(client, "teacher")
    assert client.put("/api/teacher/group", json={"student_id": stranger.id, "group": "basics"}, headers=t).status_code == 404
    names = [r["name"] for r in client.get("/api/teacher/class", params=Q, headers=t).json()["rows"]]
    assert "Out" not in names


# ---------------- parent ----------------
def test_parent_note_languages_and_privacy(client):
    p = login_staff(client, "parent")
    kids = client.get("/api/parent/children", headers=p).json()
    assert [k["name"] for k in kids] == ["Ravi K."]
    kid = kids[0]["id"]
    en = client.get("/api/parent/note", params={"student_id": kid, "lang": "en"}, headers=p).json()
    assert "Unit Test" in en["text"] and len(en["minutes_by_day"]) == 7
    assert "नमस्ते" in client.get("/api/parent/note", params={"student_id": kid, "lang": "hi"}, headers=p).json()["text"]
    assert "నమస్కారం" in client.get("/api/parent/note", params={"student_id": kid, "lang": "te"}, headers=p).json()["text"]
    assert client.get("/api/parent/note", params={"student_id": kid, "lang": "fr"}, headers=p).status_code == 422
    for banned in ("Ananya", "Imran", "rank", "score"):
        assert banned.lower() not in en["text"].lower()
    rows = client.get("/api/teacher/class", params=Q, headers=login_staff(client, "teacher")).json()["rows"]
    other = next(r["id"] for r in rows if r["sample"])
    assert client.get("/api/parent/note", params={"student_id": other}, headers=p).status_code == 403


def test_parent_note_reflects_practice_minutes(client, cur):
    s, p = login_student(client), login_staff(client, "parent")
    kid = client.get("/api/parent/children", headers=p).json()[0]["id"]
    evs = [ev(f"c-1000{i}", *qa(cur, i=i % 8)) for i in range(10)]
    client.post("/api/sync", json={"events": evs}, headers=s)
    n = client.get("/api/parent/note", params={"student_id": kid}, headers=p).json()
    assert n["total_minutes"] == 12 and n["days_practised"] == 1
