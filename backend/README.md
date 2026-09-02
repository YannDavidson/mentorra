# Mentorra Backend

The current backend entry point is `backend/agents.py`.

It is a FastAPI service that combines founder intake / mentor routing with one-on-one mentor chat, voice handling, mentor switching, and external research hooks.

## Current status

Phase 2 restores the runtime modules required by `agents.py`:

- `backend/prompts/` — versioned production prompt functions
- `backend/tavily_search.py` — Tavily deep-search adapter
- `backend/requirements.txt` — backend Python dependency manifest
- `backend/tests/test_health.py` — offline `/health` smoke test

The repository-level `prompts/` directory remains historical PDD/development provenance and is not the production runtime prompt layer.

Do not use the previous instruction to run `backend/multi_agent.py`; that file is not present in the repository.

## Run locally

Create an environment, install the backend dependencies, and start the service:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -r backend/requirements.txt
python backend/agents.py
```

The default port is `8000`, configurable through `PORT`.

## Smoke test

Run the offline backend health check with:

```bash
python -m pytest -q backend/tests/test_health.py
```

The smoke test uses local dummy credentials and must not call OpenAI, ElevenLabs, or Tavily.

## Main API surface

- `GET /health`
- `GET /api/mentors`
- `GET /api/greeting`
- `POST /api/assist`
- `POST /api/mentor-chat`
- `POST /api/mentor-assist` — compatibility route
- `POST /api/voice/speak`

`POST /api/assist` is the unified application endpoint. Requests containing a `mentor_id` enter one-on-one mentor mode; requests without a `mentor_id` enter the founder-intake / boardroom-routing flow.

## Environment variables

See the repository-level `.env.example` for the known variable names. Never commit real API keys.

## Audit

See [`../docs/REPOSITORY_AUDIT.md`](../docs/REPOSITORY_AUDIT.md) for the component inventory, remaining limitations, and recommended refactor sequence.
