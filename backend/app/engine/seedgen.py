"""Deterministic sample mastery for demo students (same generator as the phone demo)."""
from __future__ import annotations

from ..content import Curriculum


def rng(seed: int):
    s = seed & 0xFFFFFFFF

    def nxt() -> float:
        nonlocal s
        s = (s * 1664525 + 1013904223) & 0xFFFFFFFF
        return s / 4294967296

    return nxt


BASE = {"strong": 0.86, "avg": 0.68, "gap": 0.74, "weak": 0.40}


def seed_mastery(cur: Curriculum, cls: int, subject: str, archetype: str, seed: int) -> dict[str, float]:
    r = rng(seed)
    ct = cur.class_topics(cls, subject)
    allt = list(dict.fromkeys([*ct, *cur.closure_of(ct)]))
    base = BASE[archetype]
    P = {t: max(0.1, min(0.97, base + (r() - 0.5) * 0.2)) for t in allt}
    if archetype == "gap":
        pre = [t for t in cur.closure_of(ct) if t not in ct]
        if pre:
            g = pre[int(r() * len(pre))]
            P[g] = 0.28
            for t in allt:
                if t != g and cur.depends_on(t, g):
                    P[t] = max(0.15, P[t] - 0.25)
    return P
