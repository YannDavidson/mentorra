"""Versioned runtime prompts for Mentorra.

The historical prompt/PDD artifacts under the repository-level ``prompts/``
directory are preserved as development provenance. Runtime code imports prompt
functions from this package instead.
"""

from .mentors import get_katerina_catalyst_prompt, get_vincent_forge_prompt
from .routing import (
    get_completeness_checker_prompt,
    get_fact_extractor_prompt,
    get_mentor_router_prompt,
)

PROMPT_LAYER_VERSION = "2026-09-02.1"

__all__ = [
    "PROMPT_LAYER_VERSION",
    "get_vincent_forge_prompt",
    "get_katerina_catalyst_prompt",
    "get_fact_extractor_prompt",
    "get_completeness_checker_prompt",
    "get_mentor_router_prompt",
]
