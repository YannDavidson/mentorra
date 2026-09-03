"""FastAPI routes for Mentorra's ElevenLabs-backed boardroom runtime."""

from __future__ import annotations

import os
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from elevenlabs_runtime import (
    BoardroomRuntime,
    ElevenLabsRuntimeError,
    ElevenLabsTextTransport,
    load_mentor_registry,
)

router = APIRouter(prefix="/api/boardroom", tags=["boardroom"])

_transport = ElevenLabsTextTransport(api_key=os.getenv("ELEVENLABS_API_KEY", ""))
_runtime = BoardroomRuntime(load_mentor_registry(), _transport.invoke)


class StartBoardroomRequest(BaseModel):
    matter: str
    mentor_ids: List[str] = Field(min_length=1)


class UserTurnRequest(BaseModel):
    text: str
    user_name: str = "Founder"


class MentorTurnRequest(BaseModel):
    mentor_id: str
    prompt: Optional[str] = None


def _session_or_404(session_id: str):
    try:
        return _runtime.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/mentors")
def list_configured_mentors():
    return {
        "mentors": [
            {"id": mentor.id, "name": mentor.name, "configured": True}
            for mentor in _runtime.registry.values()
        ]
    }


@router.post("/sessions", status_code=201)
def start_boardroom(request: StartBoardroomRequest):
    try:
        session = _runtime.start_session(request.matter, request.mentor_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _runtime.serialize(session)


@router.get("/sessions/{session_id}")
def get_boardroom(session_id: str):
    return _runtime.serialize(_session_or_404(session_id))


@router.post("/sessions/{session_id}/user-turn")
def add_user_turn(session_id: str, request: UserTurnRequest):
    _session_or_404(session_id)
    try:
        _runtime.user_turn(session_id, request.text, request.user_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _runtime.serialize(_runtime.get_session(session_id))


@router.post("/sessions/{session_id}/mentor-turn")
def add_mentor_turn(session_id: str, request: MentorTurnRequest):
    _session_or_404(session_id)
    try:
        _runtime.mentor_turn(session_id, request.mentor_id, request.prompt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ElevenLabsRuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _runtime.serialize(_runtime.get_session(session_id))
