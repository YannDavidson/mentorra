"""Offline contract tests for the ElevenLabs boardroom runtime.

The fake transport proves the Mentorra acceptance contract without network access:
user turn -> first mentor -> canonical transcript -> second mentor receives the first
mentor's contribution in shared context.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from elevenlabs_runtime import BoardroomRuntime, ElevenLabsMentor, format_shared_context


def test_second_mentor_receives_first_mentor_shared_context() -> None:
    registry = {
        "vincent_forge": ElevenLabsMentor("vincent_forge", "Vincent Forge", "agent-vincent"),
        "katerina_catalyst": ElevenLabsMentor("katerina_catalyst", "Katerina Catalyst", "agent-katerina"),
    }
    calls = []

    def fake_invoke(agent_id: str, user_message: str, context: str) -> str:
        calls.append({"agent_id": agent_id, "user_message": user_message, "context": context})
        if agent_id == "agent-vincent":
            return "The real constraint is whether the market signal is strong enough yet."
        assert "Vincent Forge: The real constraint is whether the market signal is strong enough yet." in context
        return "I agree on validation, but I would test it with a smaller scrappy commitment first."

    runtime = BoardroomRuntime(registry, fake_invoke)
    session = runtime.start_session(
        "Should we raise now or bootstrap for another six months?",
        ["vincent_forge", "katerina_catalyst"],
    )
    runtime.user_turn(session.session_id, "We have early traction but are unsure about timing.")
    vincent = runtime.mentor_turn(session.session_id, "vincent_forge")
    katerina = runtime.mentor_turn(session.session_id, "katerina_catalyst")

    assert vincent.speaker_id == "vincent_forge"
    assert katerina.speaker_id == "katerina_catalyst"
    assert len(calls) == 2
    assert calls[0]["agent_id"] == "agent-vincent"
    assert calls[1]["agent_id"] == "agent-katerina"
    assert "Founder: We have early traction but are unsure about timing." in calls[1]["context"]
    assert vincent.text in calls[1]["context"]

    serialized = runtime.serialize(session)
    assert [entry["speaker_id"] for entry in serialized["transcript"]] == [
        "user",
        "vincent_forge",
        "katerina_catalyst",
    ]


def test_shared_context_contains_boardroom_matter() -> None:
    registry = {
        "vincent_forge": ElevenLabsMentor("vincent_forge", "Vincent Forge", "agent-vincent"),
    }
    runtime = BoardroomRuntime(registry, lambda *_: "Response")
    session = runtime.start_session("Should we launch this month?", ["vincent_forge"])
    runtime.user_turn(session.session_id, "We still have onboarding work to finish.")

    context = format_shared_context(session)
    assert "Matter: Should we launch this month?" in context
    assert "Founder: We still have onboarding work to finish." in context
