"""Mentorra production API composition.

The restored OpenAI runtime remains in agents.py. This entrypoint composes it with
the new ElevenLabs-backed boardroom routes without deleting or rewriting legacy paths.
"""

from agents import app
from boardroom_api import router as boardroom_router

app.include_router(boardroom_router)
