# Mentorra Architecture

This document describes the current conceptual architecture of the Mentorra prototype. The repository is still being consolidated, so this is a product/technical map rather than a guarantee that every component already exists as a production module.

## Decision flow

```text
Founder Context
      ↓
Router / Decision Classifier
      ↓
Relevant Mentor Agents
      ↓
Independent Mentor Briefs
      ↓
Synthesis / Tradeoff Resolution
      ↓
Decision + Prioritized Actions
```

## Core components

### Founder context
Captures the company, stage, constraints, objective, and decision being considered.

### Router
Determines which mentor perspectives are most relevant to the decision rather than invoking every available agent indiscriminately.

### Mentor agents
Provide independent strategic perspectives. Mentors are fictional pattern-based personas and should not impersonate real individuals.

### Synthesis layer
Combines the independent perspectives, identifies agreement and disagreement, resolves tradeoffs, and produces a coherent recommendation.

### Evidence / grounding
Experimental retrieval can enrich the boardroom with current external evidence such as competitors, positioning, pricing, or market signals.

### Decision record
A future production version should persist the decision, evidence considered, mentor perspectives, final recommendation, actions, and later outcome so Mentorra develops continuity across a founder's decision history.

## Current repository mapping

- `backend/` — Python agent and orchestration experiments
- `prompts/` — prompt-development history and behavioral specifications
- `frontend/` — UI experiments
- `site/` — expanded static prototype and boardroom views

## Direction of travel

The repository should gradually converge toward clear application boundaries, reproducible local development, tests around routing and structured outputs, and persistent founder/company context. Historical hackathon artifacts can eventually move into an archive area once the replacement application is stable and documented.
