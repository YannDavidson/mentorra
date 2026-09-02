# Mentorra Repository Audit

This audit captures what is actually present in the hackathon repository before structural refactoring. The goal is to distinguish active product logic from experiments, generated artifacts, and incomplete scaffolding.

## Executive summary

Mentorra is not just a static hackathon mockup. The repository contains a meaningful prototype of an AI decision boardroom for founders, including a router, mentor sessions, mentor switching, voice handling, external research hooks, and multiple UI prototypes.

Phase 2 restores the missing backend runtime layer that previously prevented `backend/agents.py` from resolving its prompt and Tavily imports. The branch now contains a versioned runtime prompt package, a Tavily adapter, a Python dependency manifest, and an offline `/health` smoke test.

The remaining work before structural refactoring is validation and consolidation rather than reconstruction of missing runtime modules. Exact dependency versions are not pinned yet, and the frontend still contains overlapping prototypes and starter scaffolding.

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

The backend currently contains:

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

## Phase 2 runtime restoration

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

Those imports are now satisfied by runtime code under `backend/`:

- `backend/prompts/__init__.py`
- `backend/prompts/mentors.py`
- `backend/prompts/routing.py`
- `backend/tavily_search.py`

The prompt functions were restored from the repository's pre-extraction history rather than recreated from scratch. The repository-level `prompts/` directory remains PDD/development provenance and is not used as the production runtime package.

The backend dependency manifest is now `backend/requirements.txt`. It captures the libraries imported by the unified backend and the smoke test, but versions are intentionally not pinned in this restoration pass, so deterministic dependency locking remains future work.

The offline smoke path is:

```bash
python -m pip install -r backend/requirements.txt
python -m pytest -q backend/tests/test_health.py
```

The smoke test sets local dummy OpenAI and ElevenLabs credentials, imports `backend/agents.py`, verifies that `/health` is registered, and invokes the route without making external API calls. This makes the test useful as an import/runtime wiring check for the restored prompt and Tavily modules as well as the FastAPI application.

A least-privilege GitHub Actions workflow has also been added for the smoke path. It uses `contents: read`, no repository secrets, and pinned action commit SHAs.

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

The top-level `prompts/` directory is **development provenance**, not runtime prompt code.

It includes several generations of backend and linking prompts, including router iterations and PDD state/core dumps. These files remain useful because they document how the hackathon implementation evolved.

The production runtime prompt layer is now:

```text
backend/
  prompts/
    __init__.py
    mentors.py
    routing.py
```

A later archival cleanup may reorganize the top-level PDD artifacts into `specs/` and `history/`, but that should not be coupled to runtime behavior.

## Canonical-component decision

For the next phase, use the following hierarchy:

1. **Canonical backend:** `backend/agents.py`
2. **Runtime prompt layer:** `backend/prompts/`
3. **Canonical UX reference:** `site/`
4. **Canonical interactive mentor prototype:** `frontend/mentorra-ui/mentor_chat.html`
5. **Development scaffolding:** `frontend/mentorra-ui` Vite package
6. **Experimental voice client:** `backend/vincent_forge.py`
7. **Prompt provenance:** top-level `prompts/`
8. **Prototype/test artifacts:** standalone HTML files pending comparison

## Recommended refactor sequence

### Phase 1 — repository hygiene

Completed on the normalization branch:

- accurate root README
- standard `.gitignore`
- removal of committed generated artifacts
- license and contribution docs
- architecture documentation
- environment variable template

### Phase 2 — restore runtime wiring

Implemented on the runtime-restoration branch:

1. restore the runtime prompt package
2. restore `tavily_search.py`
3. add `backend/requirements.txt`
4. document the verified run and test commands
5. add an offline `/health` smoke test
6. add a least-privilege backend smoke workflow

Before merge, obtain a real smoke-test execution signal and review the exact head SHA.

### Phase 3 — consolidate the frontend

1. compare `site/`, `frontend/Default.html`, `frontend/Demo.html`, and `mentor_chat.html`
2. select the product pages to preserve
3. migrate those pages into one web application
4. remove untouched Vite starter content
5. route all UI calls through the unified `/api/assist` contract

### Phase 4 — normalize runtime architecture

Only after Phase 2 validation and Phase 3 consolidation are green, move toward something like:

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
