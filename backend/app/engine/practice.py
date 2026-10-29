"""Practice flow: learn, solve (with tracing back through prerequisites), then a short check."""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from ..content import Curriculum
from .mastery import get, mean, nudge, want_level

MAX_SOLVE = 8
CHECK_LEN = 3
EXIT_TARGET = 0.85
TRACE_BELOW = 0.75      # follow a mistake pattern back when the named basic is below this
TRACE_WEAK = 0.6        # otherwise look for any weak prerequisite below this
BACK_AT = 0.7           # return to the target topic when the basic is steady again


@dataclass
class Marked:
    topic: str
    qid: str
    ok: bool
    picked: str
    right: str
    why: str
    misconception: str | None
    trace_hint: str | None   # prerequisite topic the wrong option points to, if any


def mark(cur: Curriculum, qid: str, picked: str) -> Marked | None:
    """Mark one multiple-choice answer by option text. The key never leaves the server in API flows."""
    hit = cur.question(qid)
    if not hit:
        return None
    topic, q = hit
    opt = next((o for o in q["o"] if o["t"] == picked), None)
    if opt is None:
        return None
    right = next(o["t"] for o in q["o"] if o.get("ok"))
    return Marked(topic, qid, bool(opt.get("ok")), picked, right, q["why"],
                  None if opt.get("ok") else opt.get("m"), None if opt.get("ok") else opt.get("g"))


def pool(cur: Curriculum, asked: set[str], topic: str) -> list[dict]:
    return [q for q in cur.T[topic]["qs"] if q["id"] not in asked]


def pick(cur: Curriculum, P: dict[str, float], asked: set[str], topic: str, rng: random.Random | None = None) -> dict | None:
    """Next question for a topic: the unasked one closest to the level the student is ready for."""
    rng = rng or random
    pl = pool(cur, asked, topic)
    if not pl:
        return None
    w = want_level(get(P, topic))
    rng.shuffle(pl)
    pl.sort(key=lambda q: abs(q["lvl"] - w))
    return pl[0]


def check_questions(cur: Curriculum, P: dict[str, float], topics: list[str], target: str,
                    rng: random.Random | None = None) -> list[tuple[str, dict]]:
    """Three questions, spread over the chapter's topics when it has several, with no hints."""
    rng = rng or random
    ts = topics or [target]
    allq = [(t, q) for t in ts for q in cur.T[t]["qs"]]
    w = want_level(mean(get(P, t) for t in ts))
    rng.shuffle(allq)
    allq.sort(key=lambda tq: abs(tq[1]["lvl"] - w))
    out: list[tuple[str, dict]] = []
    seen: set[str] = set()
    for t, q in allq:
        if len(out) >= CHECK_LEN:
            break
        if len(ts) > 1 and t in seen and len(seen) < min(CHECK_LEN, len(ts)):
            continue
        seen.add(t)
        out.append((t, q))
    for tq in allq:
        if len(out) >= CHECK_LEN:
            break
        if tq not in out:
            out.append(tq)
    return out


def trace_target(cur: Curriculum, P: dict[str, float], asked: set[str], target: str, m: Marked) -> str | None:
    """After a wrong answer: which prerequisite should we go back to, if any?

    1. If the wrong option names a basic and that basic is not yet solid, go there.
    2. Otherwise, if the mistake was on the target topic itself, go to its weakest unsolved prerequisite.
    """
    g = m.trace_hint
    if g and get(P, g) < TRACE_BELOW:
        return g if g != m.topic else None
    if m.topic == target:
        weak = [c for c in cur.all_pre(target) if get(P, c) < TRACE_WEAK and pool(cur, asked, c)]
        weak.sort(key=lambda c: get(P, c))
        return weak[0] if weak else None
    return None


@dataclass
class Step:
    """What the learner does next."""
    phase: str                       # 'solve' or 'check'
    focus: str
    question: tuple[str, dict] | None = None
    check: list[tuple[str, dict]] = field(default_factory=list)


def next_step(cur: Curriculum, P: dict[str, float], asked: set[str], target: str, focus: str,
              answered: int, chapter_topics: list[str] | None = None, rng: random.Random | None = None) -> Step:
    done = answered >= MAX_SOLVE or (focus == target and get(P, target) >= EXIT_TARGET and answered >= 4)
    if not done:
        for t in (focus, target):
            q = pick(cur, P, asked, t, rng)
            if q:
                return Step("solve", t if t == focus else focus, (t, q))
    return Step("check", target, check=check_questions(cur, P, chapter_topics or [target], target, rng))


@dataclass
class AnswerResult:
    marked: Marked
    before: float
    after: float
    focus: str
    trace_to: str | None
    back_to_target: bool


def apply_answer(cur: Curriculum, P: dict[str, float], asked: set[str], target: str, focus: str, m: Marked,
                 in_check: bool = False) -> AnswerResult:
    """Update mastery for one answer and decide whether to trace back or return to the target."""
    before = get(P, m.topic)
    P[m.topic] = nudge(before, m.ok)
    asked.add(m.qid)
    new_focus, trace, back = focus, None, False
    if not in_check:
        if not m.ok:
            trace = trace_target(cur, P, asked, target, m)
            if trace and trace != m.topic:
                new_focus = trace
        elif focus != target and get(P, focus) >= BACK_AT:
            new_focus, back = target, True
    return AnswerResult(m, before, P[m.topic], new_focus, trace, back)
