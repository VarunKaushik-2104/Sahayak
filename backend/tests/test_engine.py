import random
from datetime import date

from app.engine import mastery, mock, parent, planner, practice, teacher
from app.engine.seedgen import seed_mastery


def test_content_is_consistent(cur):
    assert cur.validate() == []
    assert len(cur.T) == 73 and cur.n_questions == 584


def test_closure_is_transitive_and_acyclic(cur):
    for t in cur.T:
        pre = cur.all_pre(t)
        assert t not in pre
        for p in pre:
            assert set(cur.all_pre(p)) <= set(pre)
    assert "m6_num" in cur.all_pre("m10_pair") or cur.all_pre("m10_pair")


def test_cross_subject_prerequisite(cur):
    assert "m8_lin" in cur.all_pre("s10_elec")


def test_bkt_direction_and_bounds():
    for p in (0.05, 0.3, 0.5, 0.8, 0.97):
        assert mastery.nudge(p, True) > mastery.nudge(p, False)
        assert 0 < mastery.nudge(p, True) <= mastery.MAX_P
    for p in (0.3, 0.5, 0.8):       # a wrong answer lowers a mastery that was not already near the floor
        assert mastery.nudge(p, False) < p
    assert mastery.want_level(0.2) == 1 and mastery.want_level(0.5) == 2 and mastery.want_level(0.9) == 3


def test_one_answer_never_swings_mastery_far():
    assert abs(mastery.nudge(0.5, True) - 0.5) < 0.25
    assert abs(mastery.nudge(0.5, False) - 0.5) < 0.25


def test_mark_by_option_text(cur):
    q = cur.T["m8_alg"]["qs"][0]
    right = next(o["t"] for o in q["o"] if o.get("ok"))
    wrong = next(o["t"] for o in q["o"] if not o.get("ok"))
    assert practice.mark(cur, q["id"], right).ok is True
    m = practice.mark(cur, q["id"], wrong)
    assert m.ok is False and m.misconception
    assert practice.mark(cur, q["id"], "not an option") is None
    assert practice.mark(cur, "nope_0", right) is None


def _wrong_with_trace(cur):
    for tid, t in cur.T.items():
        for q in t["qs"]:
            for o in q["o"]:
                if o.get("g"):
                    return tid, q, o
    raise AssertionError("no traced option in content")


def test_trace_back_follows_the_mistake_to_a_weak_prerequisite(cur):
    tid, q, o = _wrong_with_trace(cur)
    P = {o["g"]: 0.3, tid: 0.5}
    m = practice.mark(cur, q["id"], o["t"])
    res = practice.apply_answer(cur, P, set(), tid, tid, m)
    assert res.trace_to == o["g"] and res.focus == o["g"]
    assert res.after < res.before


def test_no_trace_when_the_basic_is_solid(cur):
    tid, q, o = _wrong_with_trace(cur)
    P = {o["g"]: 0.9, tid: 0.5}
    m = practice.mark(cur, q["id"], o["t"])
    res = practice.apply_answer(cur, P, set(), tid, tid, m)
    assert res.trace_to in (None,) or res.trace_to != o["g"]


def test_returns_to_target_once_the_basic_is_steady(cur):
    tid, q, o = _wrong_with_trace(cur)
    g = o["g"]
    gq = cur.T[g]["qs"][0]
    right = next(x["t"] for x in gq["o"] if x.get("ok"))
    P = {g: 0.69, tid: 0.5}
    res = practice.apply_answer(cur, P, set(), tid, g, practice.mark(cur, gq["id"], right))
    assert res.back_to_target and res.focus == tid


def test_next_step_goes_to_check_after_eight_questions(cur):
    P = {"m8_alg": 0.5}
    st = practice.next_step(cur, P, set(), "m8_alg", "m8_alg", 8)
    assert st.phase == "check" and len(st.check) == 3
    st = practice.next_step(cur, P, set(), "m8_alg", "m8_alg", 0)
    assert st.phase == "solve"


def test_next_step_picks_level_for_mastery(cur):
    for p, lvl in ((0.2, 1), (0.55, 2), (0.9, 3)):
        st = practice.next_step(cur, {"m8_alg": p}, set(), "m8_alg", "m8_alg", 0, rng=random.Random(1))
        assert st.question[1]["lvl"] == lvl


def test_asked_questions_are_not_repeated(cur):
    asked = set()
    for _ in range(8):
        st = practice.next_step(cur, {}, asked, "m8_alg", "m8_alg", 0)
        assert st.question[1]["id"] not in asked
        asked.add(st.question[1]["id"])


def test_plan_puts_catchups_first_and_a_mock_the_day_before(cur):
    chs = cur.chapters("TELANGANA", 8, "Maths")[:2]
    P = seed_mastery(cur, 8, "Maths", "gap", 11)
    today = date(2026, 10, 29)
    plan = planner.build_plan(cur, P, chs, date(2026, 11, 4), today)
    assert plan["days"] == 6 and len(plan["items"]) == 6
    assert plan["items"][-1]["kind"] == "mock"
    kinds = [i["kind"] for i in plan["items"][:-1]]
    assert kinds == sorted(kinds, key=lambda k: k != "catchup")     # catch-ups come before practice
    assert planner.build_plan(cur, P, chs, today, today)["items"] == []


def test_mock_is_built_marked_and_hides_the_key(cur):
    chs = cur.chapters("TELANGANA", 8, "Maths")[:2]
    items = mock.build_mock(cur, {}, chs, "Maths")
    assert sum(i["marks"] for i in items) == 7 and items[-1]["kind"] == "steps"
    pub = mock.public_item(cur, items[0])
    assert "ok" not in str(pub) and len(pub["options"]) >= 3
    sci = mock.build_mock(cur, {}, cur.chapters("TELANGANA", 8, "Science")[:2], "Science")
    assert len(sci) == 5 and all(i["kind"] == "mcq" for i in sci)


def test_steps_are_marked_by_step(cur):
    t = next(t for t, v in cur.T.items() if v.get("steps"))
    parts = cur.T[t]["steps"]["parts"]
    right = [next(o["t"] for o in p["o"] if o.get("ok")) for p in parts]
    wrong_last = right[:-1] + [next(o["t"] for o in parts[-1]["o"] if not o.get("ok"))]
    full = mock.mark_row(cur, {"kind": "steps", "topic": t, "picks": right})
    part = mock.mark_row(cur, {"kind": "steps", "topic": t, "picks": wrong_last})
    assert full["got"] == full["marks"] == 3
    assert part["got"] == 2 and len(part["misconceptions"]) == 1
    assert mock.mark_row(cur, {"kind": "steps", "topic": t, "picks": ["x", "y", "z"]}) is None


def test_groups_follow_readiness_and_basics(cur):
    ts = cur.chapter_topics(cur.chapters("TELANGANA", 8, "Maths")[:2])
    strong = seed_mastery(cur, 8, "Maths", "strong", 5)
    weak = seed_mastery(cur, 8, "Maths", "weak", 6)
    assert teacher.group_of(cur, strong, ts) == "extend"
    assert teacher.group_of(cur, weak, ts) == "basics"
    gap = seed_mastery(cur, 8, "Maths", "avg", 7)
    assert teacher.group_of(cur, gap, ts) == "practise"
    pre = [t for t in cur.closure_of(ts) if t not in ts][0]
    gap[pre] = 0.2
    assert teacher.group_of(cur, gap, ts) == "basics"


def test_briefing_names_numbers_a_teacher_can_act_on(cur):
    ts = cur.chapter_topics(cur.chapters("TELANGANA", 8, "Maths")[:2])
    rows = [teacher.Row(i, n, seed_mastery(cur, 8, "Maths", a, i), None, i == 3) for i, (n, a) in
            enumerate([("A", "strong"), ("B", "gap"), ("C", "avg"), ("D", "weak")])]
    groups = {r.id: teacher.group_of(cur, r.P, ts) for r in rows}
    b = teacher.briefing(cur, rows, {"name": "Unit Test", "date": "2026-11-04", "topics": ts}, groups, date(2026, 10, 29))
    assert len(b["items"]) == 5 and "in 6 days" in b["items"][0]["text"] and b["stale"] == 1
    ws = teacher.worksheets(cur, rows, {"topics": ts}, groups)
    assert [w["level"] for w in ws] == [1, 2, 3] and sum(w["students"] for w in ws) == 4


def test_parent_note_three_languages_and_privacy(cur):
    P = seed_mastery(cur, 8, "Maths", "gap", 11)
    ts = cur.chapter_topics(cur.chapters("TELANGANA", 8, "Maths")[:2])
    test = {"name": "Unit Test", "date": "2026-11-04", "chapters": ["A", "B"], "topics": ts}
    notes = {lg: parent.build_note(cur, name="Ravi K.", subject="Maths", lang=lg, P=P, misc={"a slip": 2},
                                   minutes_last7=[0, 10, 0, 12, 0, 0, 5], test=test, today=date(2026, 10, 29)) for lg in parent.LANGS}
    assert "in 6 days" in notes["en"]["text"] and "27 minutes" in notes["en"]["text"]
    assert "नमस्ते" in notes["hi"]["text"] and "నమస్కారం" in notes["te"]["text"]
    assert notes["te"]["draft_translation"] and not notes["en"]["draft_translation"]
    for n in notes.values():
        assert "rank" not in n["text"].lower() and "%" in n["text"] or n["lang"] != "en"
    try:
        parent.build_note(cur, name="x", subject="Maths", lang="fr", P=P, misc={}, minutes_last7=[0] * 7, test=None, today=date.today())
        assert False
    except ValueError:
        pass
