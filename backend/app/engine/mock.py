"""Mock tests: build from the weakest topics, mark by step."""
from __future__ import annotations

import random

from ..content import Curriculum
from .mastery import get, want_level


def build_mock(cur: Curriculum, P: dict[str, float], chapters: list[dict], subject: str,
               rng: random.Random | None = None) -> list[dict]:
    """Maths: 4 one-mark MCQs plus one 3-mark question marked step by step. Science: 5 MCQs."""
    rng = rng or random
    ts = sorted(cur.chapter_topics(chapters), key=lambda t: get(P, t))
    if not ts:
        return []
    with_steps = [t for t in ts if cur.T[t].get("steps")] if subject == "Maths" else []
    n_mcq = 4 if with_steps else 5
    items: list[dict] = []
    used: set[str] = set()
    for i in range(n_mcq):
        t = ts[i % len(ts)]
        qs = [q for q in cur.T[t]["qs"] if q["id"] not in used]
        rng.shuffle(qs)
        qs.sort(key=lambda q: abs(q["lvl"] - want_level(get(P, t))))
        q = qs[0] if qs else cur.T[t]["qs"][0]
        used.add(q["id"])
        items.append({"kind": "mcq", "marks": 1, "topic": t, "qid": q["id"]})
    if with_steps:
        items.append({"kind": "steps", "marks": 3, "topic": with_steps[0]})
    return items


def public_item(cur: Curriculum, item: dict, rng: random.Random | None = None) -> dict:
    """The item as the student sees it: option texts only, shuffled, no key."""
    rng = rng or random
    t = item["topic"]
    if item["kind"] == "mcq":
        _, q = cur.question(item["qid"])
        opts = [o["t"] for o in q["o"]]
        rng.shuffle(opts)
        return {"kind": "mcq", "marks": 1, "topic": t, "qid": q["id"], "q": q["q"], "options": opts}
    st = cur.T[t]["steps"]
    parts = []
    for part in st["parts"]:
        opts = [o["t"] for o in part["o"]]
        rng.shuffle(opts)
        parts.append({"label": part["label"], "prompt": part["prompt"], "options": opts})
    return {"kind": "steps", "marks": 3, "topic": t, "q": st["q"], "parts": parts}


def mark_row(cur: Curriculum, row: dict) -> dict | None:
    """Mark one submitted row. Returns None if the row does not match the curriculum.

    mcq:   {kind, qid, pick}              steps: {kind, topic, picks: [text, text, text]}
    """
    if row.get("kind") == "mcq":
        hit = cur.question(row.get("qid", ""))
        if not hit:
            return None
        t, q = hit
        opt = next((o for o in q["o"] if o["t"] == row.get("pick")), None)
        if opt is None:
            return None
        right = next(o["t"] for o in q["o"] if o.get("ok"))
        return {"kind": "mcq", "marks": 1, "got": 1 if opt.get("ok") else 0, "topic": t, "q": q["q"],
                "picked": opt["t"], "right": right, "misconceptions": [] if opt.get("ok") else [opt["m"]]}
    if row.get("kind") == "steps":
        t = row.get("topic", "")
        st = (cur.T.get(t) or {}).get("steps")
        picks = row.get("picks") or []
        if not st or len(picks) != len(st["parts"]):
            return None
        steps, got, misc = [], 0, []
        for part, pk in zip(st["parts"], picks):
            opt = next((o for o in part["o"] if o["t"] == pk), None)
            if opt is None:
                return None
            ok = bool(opt.get("ok"))
            got += ok
            if not ok:
                misc.append(opt["m"])
            steps.append({"label": part["label"], "ok": ok, "picked": pk, "right": next(o["t"] for o in part["o"] if o.get("ok"))})
        return {"kind": "steps", "marks": len(st["parts"]), "got": got, "topic": t, "q": st["q"],
                "steps": steps, "misconceptions": misc}
    return None
