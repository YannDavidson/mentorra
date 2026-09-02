# Contributing to Mentorra

Thanks for your interest in Mentorra.

Mentorra is currently transitioning from a hackathon prototype into a cleaner, more maintainable project. Contributions should preserve working prototype behavior while improving clarity, reliability, and reproducibility.

## Before contributing

1. Open or reference an issue for non-trivial changes.
2. Keep pull requests focused on one concern.
3. Avoid moving or deleting prototype files unless the change clearly documents why they are obsolete.
4. Never commit secrets, local environment files, caches, generated artifacts, or machine-specific files.

## Development principles

- Prefer small, reviewable changes.
- Preserve the historical prototype until a replacement is demonstrably functional.
- Keep mentor personas fictional and pattern-based; do not present them as real people.
- Document new environment variables and external services.
- Add tests when changing orchestration, structured outputs, or routing behavior.
- Keep prompts versioned when they materially define application behavior.

## Pull requests

A useful pull request should include:

- what changed
- why the change is needed
- how it was tested
- screenshots for meaningful UI changes
- any follow-up work intentionally left out of scope

## Repository hygiene

Do not commit:

- `.env` files
- API keys or credentials
- `__pycache__/`
- `.DS_Store`
- `node_modules/`
- build output
- local IDE configuration

## Security

If you discover a security-sensitive issue, avoid posting credentials or exploitable secrets in a public issue. Remove any exposed credential from active use immediately and rotate it with the relevant provider.
