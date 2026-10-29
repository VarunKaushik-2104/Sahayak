"""Teacher side: groups, morning briefing, three-level worksheets, after-test view."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..content import Curriculum
from .mastery import get, mean
from .planner import chapter_mastery

GROUPS = {
    "extend": {"title": "Ready to extend",
               "action": "Challenge set with application questions. Pair each student with one from Basics first for 10 minutes of peer teaching.",
               "homework": "Challenge set on the test chapters. You may be a peer tutor in class tomorrow."},
    "practise": {"title": "Keep practising",
                 "action": "Mixed practice sheet, level 2. Circulate and check the steps where marks are lost.",
                 "homework": "Mixed practice on the test chapters, level 2."},
    "basics": {"title": "Basics first",
               "action": "Teacher re-teach of 10 minutes on the weakest basic, then the level 1 sheet.",
               "homework": "Revision set on the basics behind the test chapters before tomorrow's class."},
}
STALE_DAYS = 2


@dataclass
class Row:
    id: int
    name: str
    P: dict[str, float]
    last_sync: str | None
    stale: bool
    sample: bool = False


def group_of(cur: Curriculum, P: dict[str, float], test_topics: list[str]) -> str:
    r = mean(get(P, t) for t in test_topics)
    pre = [get(P, t) for t in cur.closure_of(test_topics) if t not in test_topics]
    min_pre = min(pre) if pre else 1.0
    if r >= 0.8:
        return "extend"
    if r < 0.5 or min_pre < 0.45:
        return "basics"
    return "practise"


def class_avg(rows: list[Row], topic: str) -> float:
    return mean(get(r.P, topic) for r in rows)


def likely_slip(cur: Curriculum, topic: str) -> str:
    q = next((q for q in cur.T[topic]["qs"] if q["lvl"] == 2), cur.T[topic]["qs"][0])
    return next(o["m"] for o in q["o"] if not o.get("ok"))


def briefing(cur: Curriculum, rows: list[Row], test: dict, groups: dict[int, str], today: date) -> dict:
    """Five things a teacher can act on at 8:30 AM. Structured, plus a plain-language sentence for each."""
    ts = test["topics"]
    n = len(rows)
    days = (date.fromisoformat(test["date"]) - today).days
    pre_all = [t for t in cur.closure_of(ts) if t not in ts]
    weakest_basic = sorted(pre_all or ts, key=lambda t: class_avg(rows, t))[0]
    ready = sorted(((r, mean(get(r.P, t) for t in ts)) for r in rows), key=lambda x: x[1])
    low = [x for x in ready if x[1] < 0.6]
    gappy = sorted(ts, key=lambda t: class_avg(rows, t))[0]
    n_slip = sum(1 for r in rows if get(r.P, gappy) < 0.6)
    n_basics = sum(1 for r in rows if groups[r.id] == "basics")
    stale = [r for r in rows if r.stale]
    extend = [r for r in rows if groups[r.id] == "extend"]
    when = f"in {days} {'day' if days == 1 else 'days'}" if days > 0 else "today or past"
    low_txt = f", lowest: {', '.join(f'{r.name} {round(v * 100)}%' for r, v in low[:3])}" if low else ""
    items = [
        {"key": "test", "text": f"{test['name']} is {when}. {len(low)} of {n} students are below 60% ready{low_txt}."},
        {"key": "basics", "text": f"{n_basics} of {n} students need a basic revisited first. The weakest basic behind this test is "
                                    f"{cur.T[weakest_basic]['name']} (Class {cur.T[weakest_basic]['cls']}), averaging "
                                    f"{round(class_avg(rows, weakest_basic) * 100)}%."},
        {"key": "slip", "text": f"The test chapter with the most gaps is {cur.T[gappy]['name']}. A likely slip: "
                                 f"{likely_slip(cur, gappy)} ({n_slip} students are below 60% here)."},
        {"key": "stale", "text": f"{len(stale)} {'student has' if len(stale) == 1 else 'students have'} not synced for {STALE_DAYS} or more days, "
                                  f"so {'that row' if len(stale) == 1 else 'those rows'} may be out of date."},
        {"key": "pair", "text": (f"For the first 10 minutes: pair {' and '.join(r.name for r in extend[:2])} with students from Basics first."
                                 if extend else "For the first 10 minutes: no one is ready to extend yet, so use the Basics group for the re-teach.")},
    ]
    return {"items": items, "days": days, "below_60": len(low), "n": n, "weakest_basic": weakest_basic,
            "gappy_topic": gappy, "stale": len(stale)}


def worksheets(cur: Curriculum, rows: list[Row], test: dict, groups: dict[int, str]) -> list[dict]:
    ts = test["topics"]
    gappy = sorted(ts, key=lambda t: class_avg(rows, t))[0]
    qs = cur.T[gappy]["qs"]

    def lv(n: int) -> str:
        return next((q for q in qs if q["lvl"] == n), qs[0])["q"]

    counts = {g: sum(1 for r in rows if groups[r.id] == g) for g in GROUPS}
    return [
        {"level": 1, "group": "basics", "students": counts["basics"], "topic": gappy, "question": lv(1), "note": "Basics, one step."},
        {"level": 2, "group": "practise", "students": counts["practise"], "topic": gappy, "question": lv(2), "note": "Two steps."},
        {"level": 3, "group": "extend", "students": counts["extend"], "topic": gappy, "question": lv(3), "note": "Application."},
    ]


def after_test(cur: Curriculum, rows: list[Row], chapters: list[dict]) -> list[dict]:
    out = []
    for ch in chapters[:4]:
        wt = sorted(ch["topics"], key=lambda t: class_avg(rows, t))[0]
        avg = chapter_mastery({t: class_avg(rows, t) for t in ch["topics"]}, ch)
        out.append({"chapter": ch["name"], "class_avg": round(avg, 3), "most_marks_lost_to": likely_slip(cur, wt)})
    return out
