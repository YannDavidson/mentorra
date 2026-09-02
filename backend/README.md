# Mentorra Backend

The current backend entry point is `backend/agents.py`.

It is a FastAPI service that combines founder intake / mentor routing with one-on-one mentor chat, voice handling, mentor switching, and external research hooks.

## Current status

The backend is **not yet reproducible from a fresh clone** because two runtime modules imported by `agents.py` are not currently committed:

- `prompts` — expected to provide runtime prompt functions
- `tavily_search` — expected to provide `run_tavily_deep_search`

There is also no authoritative Python dependency manifest yet.

Do not use the previous instruction to run `backend/multi_agent.py`; that file is not present in the repository.

## Intended entry point

Once the missing runtime modules and dependency manifest are restored, the service is intended to run with:

```bash
python backend/agents.py
```

The default port is `8000`, configurable through `PORT`.

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

See [`../docs/REPOSITORY_AUDIT.md`](../docs/REPOSITORY_AUDIT.md) for the current component inventory, known blockers, and recommended refactor sequence.
