"""Live PR #4 acceptance verifier.

Requires real ELEVENLABS_API_KEY plus at least two configured mentor agent IDs.
It performs the production contract against ElevenLabs and exits non-zero if the
second mentor does not receive the first mentor's contribution in shared context.

Usage:
  python backend/scripts/verify_elevenlabs_boardroom.py \
    vincent_forge katerina_catalyst \
    "Should we raise now or bootstrap for another six months?"
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from elevenlabs_runtime import BoardroomRuntime, ElevenLabsTextTransport, load_mentor_registry


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: verify_elevenlabs_boardroom.py <first_mentor> <second_mentor> [matter]")
        return 2

    first_mentor = sys.argv[1]
    second_mentor = sys.argv[2]
    matter = sys.argv[3] if len(sys.argv) > 3 else "What is the best next move for this company?"

    api_key = (os.getenv("ELEVENLABS_API_KEY") or "").strip()
    registry = load_mentor_registry()
    missing = [mentor for mentor in (first_mentor, second_mentor) if mentor not in registry]
    if not api_key:
        print("ELEVENLABS_API_KEY is not configured")
        return 2
    if missing:
        print(f"Missing configured mentor agent IDs: {', '.join(missing)}")
        return 2

    transport = ElevenLabsTextTransport(api_key)
    runtime = BoardroomRuntime(registry, transport.invoke)
    session = runtime.start_session(matter, [first_mentor, second_mentor])

    runtime.user_turn(
        session.session_id,
        "We are testing a real Mentorra boardroom. Give your independent view on the matter.",
    )
    first = runtime.mentor_turn(session.session_id, first_mentor)
    second = runtime.mentor_turn(
        session.session_id,
        second_mentor,
        "Respond to the matter and explicitly engage with the other mentor's argument from the shared boardroom transcript.",
    )

    print(f"Session: {session.session_id}")
    print(f"Matter: {session.matter}")
    print(f"{first.speaker_name}: {first.text}")
    print(f"{second.speaker_name}: {second.text}")
    print("PASS: real mentor -> shared transcript -> second real mentor flow completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
