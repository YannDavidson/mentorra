"""ElevenLabs mentor runtime for Mentorra boardroom sessions.

This module adds a production-facing provider boundary around ElevenLabs Agents while
leaving the restored OpenAI mentor/router runtime untouched. It supports text-first
agent turns over the ElevenLabs Conversational AI WebSocket and carries the canonical
Mentorra boardroom transcript between separate mentor conversations.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import websocket

ELEVENLABS_SIGNED_URL_ENDPOINT = "https://api.elevenlabs.io/v1/convai/conversation/get-signed-url"
DEFAULT_TIMEOUT_SECONDS = 45


@dataclass(frozen=True)
class ElevenLabsMentor:
    id: str
    name: str
    agent_id: str


@dataclass
class TranscriptEntry:
    speaker_id: str
    speaker_name: str
    role: str
    text: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> Dict[str, str]:
        return {
            "speaker_id": self.speaker_id,
            "speaker_name": self.speaker_name,
            "role": self.role,
            "text": self.text,
            "created_at": self.created_at,
        }


@dataclass
class BoardroomSession:
    session_id: str
    matter: str
    mentor_ids: List[str]
    transcript: List[TranscriptEntry] = field(default_factory=list)


class ElevenLabsRuntimeError(RuntimeError):
    pass


def load_mentor_registry(env: Optional[Dict[str, str]] = None) -> Dict[str, ElevenLabsMentor]:
    source = env if env is not None else os.environ
    definitions = {
        "vincent_forge": ("Vincent Forge", "ELEVENLABS_AGENT_VINCENT_FORGE"),
        "katerina_catalyst": ("Katerina Catalyst", "ELEVENLABS_AGENT_KATERINA_CATALYST"),
        "sophia_architect": ("Sophia Architect", "ELEVENLABS_AGENT_SOPHIA_ARCHITECT"),
        "adrian_insight": ("Adrian Insight", "ELEVENLABS_AGENT_ADRIAN_INSIGHT"),
    }
    registry: Dict[str, ElevenLabsMentor] = {}
    for mentor_id, (name, variable) in definitions.items():
        agent_id = (source.get(variable) or "").strip()
        if agent_id:
            registry[mentor_id] = ElevenLabsMentor(mentor_id, name, agent_id)
    return registry


def format_shared_context(session: BoardroomSession, max_entries: int = 24) -> str:
    recent = session.transcript[-max_entries:]
    lines = [
        "MENTORRA BOARDROOM CONTEXT",
        f"Matter: {session.matter}",
        "Shared transcript:",
    ]
    if not recent:
        lines.append("(No prior turns yet.)")
    else:
        for entry in recent:
            lines.append(f"{entry.speaker_name}: {entry.text}")
    lines.append(
        "Respond to the current boardroom turn with awareness of this shared discussion. "
        "Do not pretend you personally said another mentor's words."
    )
    return "\n".join(lines)


class ElevenLabsTextTransport:
    """One-turn authenticated text transport for an ElevenLabs Agent conversation."""

    def __init__(self, api_key: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS):
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def _get_signed_url(self, agent_id: str) -> str:
        query = urlencode({"agent_id": agent_id})
        request = Request(
            f"{ELEVENLABS_SIGNED_URL_ENDPOINT}?{query}",
            headers={"xi-api-key": self.api_key},
            method="GET",
        )
        try:
            with urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise ElevenLabsRuntimeError(f"Unable to obtain ElevenLabs signed URL: {exc}") from exc

        signed_url = (payload.get("signed_url") or "").strip()
        if not signed_url:
            raise ElevenLabsRuntimeError("ElevenLabs signed URL response was empty")
        return signed_url

    def invoke(self, agent_id: str, user_message: str, context: str) -> str:
        if not self.api_key:
            raise ElevenLabsRuntimeError("ELEVENLABS_API_KEY is not configured")
        if not agent_id:
            raise ElevenLabsRuntimeError("ElevenLabs agent_id is required")
        if not user_message.strip():
            raise ElevenLabsRuntimeError("user_message is required")

        response_text: Dict[str, Optional[str]] = {"value": None}
        failure: Dict[str, Optional[str]] = {"value": None}
        finished = threading.Event()
        signed_url = self._get_signed_url(agent_id)

        def on_open(ws: websocket.WebSocketApp) -> None:
            ws.send(json.dumps({"type": "conversation_initiation_client_data"}))

        def on_message(ws: websocket.WebSocketApp, raw: str) -> None:
            message = json.loads(raw)
            message_type = message.get("type")

            if message_type == "conversation_initiation_metadata":
                if context:
                    ws.send(json.dumps({"type": "contextual_update", "text": context}))
                ws.send(json.dumps({"type": "user_message", "text": user_message}))
                return

            if message_type == "agent_response":
                text = (message.get("agent_response_event") or {}).get("agent_response")
                if text:
                    response_text["value"] = text.strip()
                return

            if message_type == "agent_response_complete":
                finished.set()
                ws.close()
                return

            if message_type == "ping":
                event_id = (message.get("ping_event") or {}).get("event_id")
                ws.send(json.dumps({"type": "pong", "event_id": event_id}))
                return

            if message_type == "client_error":
                failure["value"] = json.dumps(message)
                finished.set()
                ws.close()

        def on_error(_ws: websocket.WebSocketApp, error: Any) -> None:
            failure["value"] = str(error)
            finished.set()

        def on_close(_ws: websocket.WebSocketApp, _code: Any, _reason: Any) -> None:
            finished.set()

        ws = websocket.WebSocketApp(
            signed_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )

        worker = threading.Thread(target=ws.run_forever, daemon=True)
        worker.start()
        if not finished.wait(self.timeout_seconds):
            ws.close()
            raise ElevenLabsRuntimeError("ElevenLabs mentor turn timed out")
        worker.join(timeout=2)

        if failure["value"]:
            raise ElevenLabsRuntimeError(f"ElevenLabs mentor turn failed: {failure['value']}")
        if not response_text["value"]:
            raise ElevenLabsRuntimeError("ElevenLabs mentor returned no text response")
        return response_text["value"] or ""


class BoardroomRuntime:
    """Canonical shared transcript plus provider-backed mentor turns."""

    def __init__(
        self,
        registry: Dict[str, ElevenLabsMentor],
        invoke_mentor: Callable[[str, str, str], str],
    ):
        self.registry = registry
        self.invoke_mentor = invoke_mentor
        self.sessions: Dict[str, BoardroomSession] = {}
        self.lock = threading.Lock()

    def start_session(self, matter: str, mentor_ids: List[str]) -> BoardroomSession:
        cleaned_matter = matter.strip()
        selected = list(dict.fromkeys(mentor_ids))
        if not cleaned_matter:
            raise ValueError("matter is required")
        if not selected:
            raise ValueError("at least one mentor is required")
        unknown = [mentor_id for mentor_id in selected if mentor_id not in self.registry]
        if unknown:
            raise ValueError(f"unconfigured mentor ids: {', '.join(unknown)}")

        session = BoardroomSession(
            session_id=str(uuid.uuid4()),
            matter=cleaned_matter,
            mentor_ids=selected,
        )
        with self.lock:
            self.sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> BoardroomSession:
        with self.lock:
            session = self.sessions.get(session_id)
        if not session:
            raise KeyError(f"unknown boardroom session: {session_id}")
        return session

    def user_turn(self, session_id: str, text: str, user_name: str = "Founder") -> TranscriptEntry:
        session = self.get_session(session_id)
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("text is required")
        entry = TranscriptEntry("user", user_name, "user", cleaned)
        with self.lock:
            session.transcript.append(entry)
        return entry

    def mentor_turn(self, session_id: str, mentor_id: str, prompt: Optional[str] = None) -> TranscriptEntry:
        session = self.get_session(session_id)
        if mentor_id not in session.mentor_ids:
            raise ValueError(f"mentor is not seated in this boardroom: {mentor_id}")
        mentor = self.registry.get(mentor_id)
        if not mentor:
            raise ValueError(f"mentor is not configured: {mentor_id}")

        context = format_shared_context(session)
        turn_prompt = (prompt or "Respond to the latest boardroom discussion.").strip()
        reply = self.invoke_mentor(mentor.agent_id, turn_prompt, context).strip()
        if not reply:
            raise ElevenLabsRuntimeError(f"{mentor.name} returned an empty response")

        entry = TranscriptEntry(mentor.id, mentor.name, "mentor", reply)
        with self.lock:
            session.transcript.append(entry)
        return entry

    def serialize(self, session: BoardroomSession) -> Dict[str, Any]:
        return {
            "session_id": session.session_id,
            "matter": session.matter,
            "mentor_ids": session.mentor_ids,
            "transcript": [entry.as_dict() for entry in session.transcript],
        }
