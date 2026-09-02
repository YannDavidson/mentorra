# Mentorra

**Mentorra is an AI decision boardroom for founders.** It brings multiple specialized AI mentor perspectives into one structured decision process so founders can move from uncertainty and conflicting advice to a clear, prioritized course of action.

Mentorra began as a hackathon prototype built in Palo Alto in January 2026. The repository preserves that prototype while serving as the foundation for continued development.

## Why Mentorra

Founders rarely suffer from a shortage of information. They suffer from fragmented advice, unresolved tradeoffs, limited access to experienced mentors, and difficulty turning strategic thinking into execution.

Mentorra is designed around a different interaction model from a single AI chat. A founder provides context once, a routing layer selects relevant mentor perspectives, specialized agents reason independently, and a synthesis layer reconciles their recommendations into one actionable output.

## Core concept

```text
Founder context
      ↓
Decision / routing layer
      ↓
Specialized mentor agents
      ↓
Independent perspectives
      ↓
Synthesis and tradeoff resolution
      ↓
Prioritized founder decision / execution plan
```

The long-term idea is a persistent **decision boardroom**: a place where founders can bring consequential questions, compare expert viewpoints, inspect the reasoning behind recommendations, and maintain continuity across decisions over time.

## Current prototype

This repository contains the original hackathon implementation and later experiments. It currently includes:

- Python-based mentor and orchestration logic
- Prompt-development artifacts used to shape agent behavior
- Static HTML interface experiments and demo pages
- A larger `site/` prototype containing boardroom and mentor views
- Early work on deeper search / external grounding

The project is still prototype-stage. Some folders represent experiments rather than a single production application, and the repository is being normalized incrementally without discarding the original hackathon work.

## Repository structure

```text
mentorrahackaton/
├── backend/            # Python agent and mentor logic
├── frontend/           # Frontend and HTML prototype experiments
├── prompts/            # Prompt-driven development artifacts
├── site/               # Broader static site / boardroom prototype
├── docs/               # Product and architecture documentation
├── .gitignore
├── CONTRIBUTING.md
├── LICENSE
└── README.md
```

### `backend/`
Contains the Python implementation of Mentorra's mentor agents and orchestration experiments.

### `frontend/`
Contains early interface prototypes and the evolving Mentorra UI implementation.

### `prompts/`
Contains prompt artifacts produced during prompt-driven development. These files document how parts of the prototype were generated and refined and should be treated as part of the project's development history.

### `site/`
Contains the larger static prototype used to explore boardrooms, individual mentor experiences, and demo flows.

## Mentor model

Mentorra's AI mentors are fictional, pattern-based strategic personas rather than impersonations of real people. The prototype includes perspectives such as:

- **Adrian Insight** — focus, product-market fit, and startup fundamentals
- **Katerina Catalyst** — revenue, sales, pricing, and founder resilience
- **Sophia Architect** — product experience, trust, narrative, and differentiation
- **Vincent Forge** — ambitious execution and difficult-builder problems

A mentor can produce a structured perspective that includes diagnosis, key insight, likely mistakes, recommended action, and immediate next steps. The boardroom layer can then synthesize those perspectives rather than forcing the founder to reconcile multiple independent AI conversations manually.

## Product direction

The prototype started with a simple question:

> What if every founder could convene a high-quality advisory board whenever an important decision had to be made?

The product can evolve beyond one-shot mentorship into infrastructure for founder decision-making, including:

- persistent company and founder context
- decision history and institutional memory
- configurable boardrooms for different problem types
- evidence and market grounding
- explicit disagreement and tradeoff resolution between agents
- decision records and follow-through
- recurring strategic reviews
- specialized boardrooms for fundraising, product, hiring, go-to-market, finance, and operations

## Development status

Mentorra is an early-stage prototype under active reorganization. The current priority is to preserve what was built during the hackathon while turning the repository into a clean base for continued engineering.

The normalization work includes clearer documentation, conventional repository hygiene, removal of generated artifacts from version control, and separation between historical experiments and the eventual production application.

## Running the project

The repository does not yet expose a single canonical production setup command. Different parts of the hackathon prototype were built independently.

Until the application is consolidated, inspect the README or source files inside the relevant folder before running an individual component. A reproducible local development workflow will be added as the frontend and backend are normalized.

## Contributing

Contributions, technical feedback, architecture suggestions, and product discussion are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## Origin

Mentorra was created during a Palo Alto hackathon in January 2026 as an experiment in multi-agent founder mentorship and decision support. The hackathon repository is intentionally being evolved rather than replaced so the project's technical and product history remains visible.

## License

This repository is licensed under the MIT License. See [LICENSE](LICENSE).

---

**Mentorra — an AI decision boardroom for founders.**
