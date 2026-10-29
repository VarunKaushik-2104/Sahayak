"""Revision plan to a test date, and readiness numbers."""
from __future__ import annotations

from datetime import date, timedelta

from ..content import Curriculum
from .mastery import get, mean

PLAN_DAYS = 14
CATCHUP_BELOW = 0.6


def chapter_mastery(P: dict[str, float], chapter: dict) -> float:
    return mean(get(P, t) for t in chapter["topics"])


def readiness(cur: Curriculum, P: dict[str, float], chapters: list[dict]) -> float:
    return mean(get(P, t) for t in cur.chapter_topics(chapters))


def weak_prereqs(cur: Curriculum, P: dict[str, float], chapter: dict, below: float = CATCHUP_BELOW) -> list[str]:
    own = set(chapter["topics"])
    pre = list(dict.fromkeys(g for t in chapter["topics"] for g in cur.all_pre(t)))
    return sorted((t for t in pre if t not in own and get(P, t) < below), key=lambda t: get(P, t))


def build_plan(cur: Curriculum, P: dict[str, float], chapters: list[dict], test_date: date, today: date) -> dict:
    """One item per day: catch-ups on weak basics first, then the weakest chapters, mock the day before."""
    days = (test_date - today).days
    if days <= 0:
        return {"days": days, "items": []}
    in_test = set(cur.chapter_topics(chapters))
    pre: list[dict] = []
    for ch in chapters:
        for t in ch["topics"]:
            for g in cur.all_pre(t):
                if g not in in_test and get(P, g) < CATCHUP_BELOW and not any(x["topic"] == g for x in pre):
                    pre.append({"topic": g, "chapter": ch["name"]})
    pre.sort(key=lambda x: get(P, x["topic"]))
    need = {ch["name"]: 1 - chapter_mastery(P, ch) + 0.15 for ch in chapters}
    items: list[dict] = []
    for i in range(min(days, PLAN_DAYS)):
        when = today + timedelta(days=i)
        if i == days - 1:
            items.append({"date": when.isoformat(), "kind": "mock", "title": "Mock test, then fix the slips",
                          "why": "Timed, marked by steps where the subject allows", "minutes": 25})
            continue
        if pre:
            x = pre.pop(0)
            items.append({"date": when.isoformat(), "kind": "catchup", "topic": x["topic"],
                          "title": f"Catch-up: {cur.T[x['topic']]['name']}",
                          "why": f"{round(get(P, x['topic']) * 100)}% now, and {x['chapter']} builds on it", "minutes": 15})
            continue
        ch = max(chapters, key=lambda c: need[c["name"]])
        need[ch["name"]] -= 0.35
        items.append({"date": when.isoformat(), "kind": "practice", "chapter": ch["name"],
                      "title": f"Practise {ch['name']}", "why": f"{round(chapter_mastery(P, ch) * 100)}% now", "minutes": 20})
    return {"days": days, "items": items}
