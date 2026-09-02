# Mentorra Repository Audit

This audit captures what is actually present in the hackathon repository before any structural refactor. The goal is to distinguish active product logic from experiments, generated artifacts, and incomplete scaffolding.

## Executive summary

Mentorra is not just a static hackathon mockup. The repository contains a meaningful prototype of an AI decision boardroom for founders, including a router, mentor sessions, mentor switching, voice handling, external research hooks, and multiple UI prototypes.

However, the repository is **not currently reproducible from a fresh clone**. Some imports required by the unified backend are missing from source control, there is no authoritative Python dependency file, and several frontend paths overlap or represent abandoned scaffolding.

The immediate priority should be restoration and consolidation before a large-scale folder move.

## Canonical backend candidate

`backend/agents.py` is the strongest candidate for the canonical backend.

It identifies itself as the "Mentorra Unified Backend" and combines two earlier concepts:

- founder intake / boardroom routing
- one-on-one mentor conversations

The current FastAPI surface includes:

- `GET /health`
- `GET /api/mentors`
- `GET /api/greeting`
- `GET /api/session/{session_id}`
- `GET /api/router-session/{session_id}`
- `POST /api/assist`
- `POST /api/mentor-chat`
- `POST /api/mentor-assist` (compatibility route)
- `POST /api/voice/speak`

`POST /api/assist` is the clearest application boundary: requests containing `mentor_id` are routed to one-on-one mentor chat; other requests enter boardroom intake/routing.

### Implemented backend capabilities

The file currently contains:

- FastAPI application setup
- founder-profile and router request models
- router session state
- required founder-context fields
- mentor routing
- mentor aliases and switching
- in-memory mentor sessions
- OpenAI chat-completions calls
- tool execution loop
- Tavily deep-search hook
- ElevenLabs text-to-speech
- OpenAI Whisper transcription
- text and voice request modes

### Current mentor coverage

The boardroom router knows about four mentor identities:

- Vincent Forge
- Katerina Catalyst
- Sophia Architect
- Adrian Insight

The one-on-one chat implementation currently supports only:

- Vincent Forge
- Katerina Catalyst

That mismatch is important. It means the routing layer is conceptually ahead of the implemented interactive mentor layer.

## Backend blockers

A fresh checkout cannot currently run `backend/agents.py` as committed.

### Missing source modules

`agents.py` imports:

```python
from prompts import (
    get_vincent_forge_prompt,
    get_katerina_catalyst_prompt,
    get_fact_extractor_prompt,
    get_completeness_checker_prompt,
    get_mentor_router_prompt,
)
from tavily_search import run_tavily_deep_search
```

No committed `prompts.py` or `tavily_search.py` exists in the repository.

The top-level `prompts/` directory contains Prompt-Driven Development artifacts, but it is not the Python module expected by this import statement.

### Missing reproducible environment

The backend uses at least:

- FastAPI
- Uvicorn
- python-dotenv
- OpenAI Python SDK
- ElevenLabs Python SDK
- Pydantic
- Tavily integration code

`backend/vincent_forge.py` additionally uses:

- websocket-client
- PyAudio

There is currently no authoritative `requirements.txt` or `pyproject.toml`, so dependency versions cannot be reliably reconstructed.

### Stale backend README

`backend/README.md` instructs contributors to run `backend/multi_agent.py`, but that file is not present. The actual unified entry point appears to be:

```bash
python backend/agents.py
```

This should be corrected only after the missing modules are restored or recreated.

## `backend/vincent_forge.py`

This file is best classified as an **experimental voice client**, not the core backend.

It opens an ElevenLabs conversational WebSocket, streams microphone PCM audio through PyAudio, and plays returned audio locally. It overlaps with voice functionality now embedded in `agents.py` but follows a different architecture.

Recommendation: retain it for now, but eventually move it under an `experiments/voice/` or `archive/hackathon/` area once the supported voice path is confirmed.

## Frontend inventory

### `frontend/mentorra-ui/`

This folder is mixed.

The Vite package and proxy configuration are useful development scaffolding. `vite.config.js` proxies `/api` and `/health` to the backend on port 8000.

However, `src/main.js` is still the default Vite starter application. It renders Vite/JavaScript logos, a counter, and documentation links. It should **not** be treated as Mentorra's canonical application source.

The same folder also contains `mentor_chat.html`, which is a genuine Mentorra UI and talks to `/api/assist`. That page is much closer to the real application than the Vite starter source.

This means the folder currently mixes a real Mentorra prototype with unused starter scaffolding.

### `frontend/Default.html`, `frontend/Demo.html`, `frontend/test_file.html`

These are standalone prototype/test artifacts. They should not be renamed or removed until compared against the `site/` versions and checked for unique behavior.

`test_file.html` is clearly an API-development/testing utility rather than a product page.

## `site/` inventory

`site/` is the broadest product-facing static prototype in the repository. It includes:

- demo pages
- boardroom page(s)
- mentor directory/views
- individual mentor pages for Vincent, Katerina, Sophia, and Adrian

The `site/Demo/Index.html` copy captures the current product idea particularly well: users can start with one mentor for fast clarity or escalate to multiple mentors for more complex decisions.

Because `site/` has the widest product surface, it should be treated as the **canonical UX reference** during consolidation, even if its implementation is not yet the long-term web architecture.

## Prompt lineage

The top-level `prompts/` directory should be treated primarily as **development provenance**, not runtime prompt code.

It includes several generations of backend and linking prompts, including router iterations and PDD state/core dumps. These files are useful because they document how the hackathon implementation evolved, but they should not remain mixed indefinitely with the runtime prompt package.

Recommended future separation:

```text
prompts/
  runtime/        # prompts actually imported by the application
  specs/          # behavioral / prompt specifications
  history/        # hackathon/PDD generations and old revisions
```

Do not perform this move until the missing runtime prompt functions have been reconstructed and tested.

## Canonical-component decision

For the next phase, use the following hierarchy:

1. **Canonical backend:** `backend/agents.py`
2. **Canonical UX reference:** `site/`
3. **Canonical interactive mentor prototype:** `frontend/mentorra-ui/mentor_chat.html`
4. **Development scaffolding:** `frontend/mentorra-ui` Vite package
5. **Experimental voice client:** `backend/vincent_forge.py`
6. **Prompt provenance:** top-level `prompts/`
7. **Prototype/test artifacts:** standalone HTML files pending comparison

## Recommended refactor sequence

### Phase 1 — repository hygiene

Already started in the normalization PR:

- accurate root README
- standard `.gitignore`
- remove committed generated artifacts
- license and contribution docs
- architecture documentation

### Phase 2 — restore reproducibility

Before moving runtime files:

1. reconstruct or recover the missing runtime `prompts` module
2. reconstruct or recover `tavily_search.py`
3. create an authoritative Python dependency manifest
4. create `.env.example` with variable names only
5. update `backend/README.md` with verified run commands
6. perform a clean-clone startup test
7. add a minimal backend smoke test for `/health`

### Phase 3 — consolidate the frontend

1. compare `site/`, `frontend/Default.html`, `frontend/Demo.html`, and `mentor_chat.html`
2. select the product pages to preserve
3. migrate those pages into one web application
4. remove untouched Vite starter content
5. route all UI calls through the unified `/api/assist` contract

### Phase 4 — normalize runtime architecture

Only after Phases 2 and 3 are green, move toward something like:

```text
backend/
  app/
    api/
    agents/
    boardroom/
    prompts/
    retrieval/
    voice/
    sessions/
  tests/

web/
  ...

prompts/
  specs/
  history/

docs/
experiments/
```

The exact framework for `web/` should be decided from the preserved product UI, not imposed on the hackathon repository prematurely.

## Product architecture insight

The implementation shows that Mentorra already contains two related but distinct products:

1. **Mentor mode** — a founder selects or is routed to a specialist and has an ongoing conversation.
2. **Boardroom mode** — founder context is collected, multiple perspectives can be selected, and the system is intended to resolve a decision.

The stronger long-term product is the decision infrastructure connecting those modes: understand the decision, assemble the right perspectives, ground them in evidence, expose disagreement, synthesize a recommendation, record the choice, and eventually learn from its outcome.

That decision loop should guide the refactor more than preserving any specific hackathon folder name.
