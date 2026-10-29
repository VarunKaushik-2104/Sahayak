"""The curriculum: topics, prerequisite graph, questions, and board chapter maps.

Loaded once from data/curriculum.json (built from content_src/ by scripts/build_curriculum.py).
"""
from __future__ import annotations

import hashlib
import json
from functools import cached_property
from pathlib import Path
from typing import Any

SUBJECTS = ("Maths", "Science")
BOARDS = ("CBSE", "ICSE", "TELANGANA")


class Curriculum:
    def __init__(self, raw: dict[str, Any], raw_bytes: bytes | None = None):
        self.T: dict[str, dict] = raw["T"]
        self.B: dict[str, dict] = raw["B"]
        blob = raw_bytes if raw_bytes is not None else json.dumps(raw, sort_keys=True).encode()
        self.version = hashlib.sha256(blob).hexdigest()[:16]
        self._closure: dict[str, list[str]] = {}
        self._q_index: dict[str, tuple[str, dict]] = {
            q["id"]: (tid, q) for tid, t in self.T.items() for q in t["qs"]
        }

    # ---- loading -----------------------------------------------------------------
    @classmethod
    def load(cls, path: Path) -> "Curriculum":
        raw_bytes = Path(path).read_bytes()
        return cls(json.loads(raw_bytes), raw_bytes)

    # ---- graph -------------------------------------------------------------------
    def has(self, topic: str) -> bool:
        return topic in self.T

    def all_pre(self, topic: str) -> list[str]:
        """Every prerequisite of a topic, transitively, in discovery order."""
        if topic in self._closure:
            return self._closure[topic]
        seen: dict[str, None] = {}

        def walk(x: str) -> None:  # pre-order DFS, same discovery order as the phone engine
            for y in self.T[x]["pre"]:
                if y not in seen:
                    seen[y] = None
                    walk(y)

        walk(topic)
        self._closure[topic] = list(seen)
        return self._closure[topic]

    def closure_of(self, topics: list[str]) -> list[str]:
        out: dict[str, None] = {}
        for t in topics:
            for g in self.all_pre(t):
                out[g] = None
        return list(out)

    def depends_on(self, topic: str, basic: str) -> bool:
        return basic in self.all_pre(topic)

    def class_topics(self, cls: int, subject: str) -> list[str]:
        return [k for k, t in self.T.items() if t["cls"] == cls and t["sub"] == subject]

    # ---- chapters ----------------------------------------------------------------
    def chapters(self, board: str, cls: int, subject: str) -> list[dict]:
        return self.B.get(board, {}).get("classes", {}).get(str(cls), {}).get(subject, [])

    @staticmethod
    def chapter_topics(chapters: list[dict]) -> list[str]:
        return list(dict.fromkeys(t for c in chapters for t in c["topics"]))

    # ---- questions ---------------------------------------------------------------
    def question(self, qid: str) -> tuple[str, dict] | None:
        return self._q_index.get(qid)

    @cached_property
    def n_questions(self) -> int:
        return len(self._q_index)

    def name(self, topic: str, lang: str = "en") -> str:
        t = self.T[topic]
        return t["te"] if lang == "te" else t["hi"] if lang == "hi" else t["name"]

    # ---- integrity ---------------------------------------------------------------
    def validate(self) -> list[str]:
        """Return a list of problems; empty means the content is internally consistent."""
        errs: list[str] = []
        for tid, t in self.T.items():
            for p in t["pre"]:
                if p not in self.T:
                    errs.append(f"{tid}: unknown prerequisite {p}")
            if len(t["qs"]) < 6:
                errs.append(f"{tid}: only {len(t['qs'])} questions")
            for q in t["qs"]:
                oks = [o for o in q["o"] if o.get("ok")]
                if len(oks) != 1:
                    errs.append(f"{q['id']}: expected exactly one correct option")
                texts = [o["t"] for o in q["o"]]
                if len(set(texts)) != len(texts):
                    errs.append(f"{q['id']}: duplicate option text")
                for o in q["o"]:
                    if not o.get("ok") and not o.get("m"):
                        errs.append(f"{q['id']}: wrong option without a misconception tag")
                    g = o.get("g")
                    if g and g not in self.all_pre(tid):
                        errs.append(f"{q['id']}: trace target {g} is not a prerequisite of {tid}")
        # acyclic
        state: dict[str, int] = {}

        def visit(x: str) -> bool:
            if state.get(x) == 1:
                return False
            if state.get(x) == 2:
                return True
            state[x] = 1
            for y in self.T[x]["pre"]:
                if y in self.T and not visit(y):
                    return False
            state[x] = 2
            return True

        for tid in self.T:
            if not visit(tid):
                errs.append(f"cycle through {tid}")
                break
        for b, bd in self.B.items():
            for c, subs in bd["classes"].items():
                for s, chs in subs.items():
                    for ch in chs:
                        for t in ch["topics"]:
                            if t not in self.T:
                                errs.append(f"{b} class {c} {s} '{ch['name']}': unknown topic {t}")
        return errs


_curriculum: Curriculum | None = None


def get_curriculum() -> Curriculum:
    global _curriculum
    if _curriculum is None:
        from .config import settings

        _curriculum = Curriculum.load(settings.curriculum_path)
    return _curriculum
