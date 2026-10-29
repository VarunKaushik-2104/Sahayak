"""Mastery estimate for one topic: a Bayesian-knowledge-tracing update, damped so one answer never swings it."""
from __future__ import annotations

SLIP, GUESS, LEARN = 0.10, 0.22, 0.12
DAMP = 0.55
PRIOR = 0.5
MAX_P = 0.98


def bkt(p: float, ok: bool) -> float:
    """Posterior probability the student knows the topic after one answer, plus the chance they learnt it meanwhile."""
    p_correct = p * (1 - SLIP) + (1 - p) * GUESS
    post = p * (1 - SLIP) / p_correct if ok else p * SLIP / (1 - p_correct)
    return min(MAX_P, post + (1 - post) * LEARN)


def nudge(p: float, ok: bool) -> float:
    return p + DAMP * (bkt(p, ok) - p)


def want_level(p: float) -> int:
    """Question difficulty to ask next: 1 basic, 2 standard, 3 application."""
    return 1 if p < 0.4 else 2 if p < 0.7 else 3


def mean(xs) -> float:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def get(P: dict[str, float], topic: str) -> float:
    return P.get(topic, PRIOR)
