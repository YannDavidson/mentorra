"""Offline smoke tests for the Mentorra backend."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# The clients are constructed at import time, but this smoke test must never use
# real credentials or make external API calls.
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("ELEVENLABS_API_KEY", "test-elevenlabs-key")

import agents  # noqa: E402


def test_health_route_exists_and_runs_without_network() -> None:
    route = next((r for r in agents.app.routes if getattr(r, "path", None) == "/health"), None)
    assert route is not None, "Expected GET /health route to be registered"

    result = route.endpoint()
    if asyncio.iscoroutine(result):
        result = asyncio.run(result)

    assert result is not None
