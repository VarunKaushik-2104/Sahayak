"""Curriculum for the phones. One cacheable bundle, plus small lookups."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ..config import settings
from ..content import BOARDS, SUBJECTS, Curriculum
from ..deps import curriculum

router = APIRouter(prefix="/content", tags=["content"])


@router.get("/bundle")
def bundle(request: Request, cur: Curriculum = Depends(curriculum)):
    """The whole syllabus (topics, prerequisites, questions, chapter maps). The phone caches it and works offline."""
    etag = f'"{cur.version}"'
    headers = {"ETag": etag, "Cache-Control": "public, max-age=3600"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(settings.curriculum_path.read_bytes(), media_type="application/json", headers=headers)


@router.get("/version")
def version(cur: Curriculum = Depends(curriculum)):
    return {"version": cur.version, "topics": len(cur.T), "questions": cur.n_questions}


@router.get("/chapters")
def chapters(board: str, cls: int, subject: str, cur: Curriculum = Depends(curriculum)):
    if board not in BOARDS or subject not in SUBJECTS or not 6 <= cls <= 10:
        raise HTTPException(422, "Unknown board, class or subject")
    return cur.chapters(board, cls, subject)


@router.get("/topics/{topic_id}")
def topic(topic_id: str, cur: Curriculum = Depends(curriculum)):
    if not cur.has(topic_id):
        raise HTTPException(404, "Unknown topic")
    t = cur.T[topic_id]
    return {k: t[k] for k in ("id", "sub", "cls", "name", "pre", "te", "hi", "lesson")} | {"prerequisites_all": cur.all_pre(topic_id)}
