"""
Mentorra Unified Backend — router + mentor chat on one uvicorn server
--------------------------------------------------------------------
Combines:
  - Router / boardroom intake (from first_assistant.py)
  - 1-on-1 mentor chat with Vincent Forge & Katerina Catalyst (from multi_agent.py)

Run:
  python backend/agents.py

Environment variables:
  OPENAI_API_KEY
  ELEVENLABS_API_KEY
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import threading
from dataclasses import dataclass, field
from time import time
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from dotenv import load_dotenv
from elevenlabs import ElevenLabs
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import APIError, OpenAI
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Env + app setup
# ---------------------------------------------------------------------------
load_dotenv()

if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY is missing in .env")
if not os.getenv("ELEVENLABS_API_KEY"):
    raise ValueError("ELEVENLABS_API_KEY is missing in .env")

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

app = FastAPI(title="Mentorra Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_MODEL = os.getenv("MENTORRA_MODEL", "gpt-4o-mini")
ROUTER_MODEL = os.getenv("ROUTER_MODEL", "gpt-4-turbo")
MAX_TOOL_ITERATIONS = 6

# =============================================================================
# ROUTER — models & roster (first_assistant)
# =============================================================================

REQUIRED_ROUTER_FIELDS = [
    "GOAL",
    "MAIN_BARRIER",
    "DOMAIN",
    "MENTORSHIP_VALUES",
    "RISK_PROFILE",
    "FEEDBACK_STYLE",
    "RESILIENCE_SIGNAL",
    "EXPERIENCE_LEVEL",
]


class FounderProfile(BaseModel):
    industry: Optional[str] = None
    stage: Optional[str] = None
    key_challenges: List[str] = Field(default_factory=list)


class UnifiedAssistRequest(BaseModel):
    session_id: Optional[str] = None
    mode: Literal["text", "voice"] = "text"
    user_message: Optional[str] = None
    audio_base64: Optional[str] = None
    audio_mime_type: Optional[str] = "audio/webm"
    audio_filename: Optional[str] = None
    founder_profile: Optional[FounderProfile] = None
    active_mentor_track: Optional[str] = None
    memory_context: Optional[str] = ""
    set_preferred_mentor: Optional[bool] = False
    selected_agents: List[str] = Field(default_factory=list)
    voice_id: Optional[str] = "JBFqnCBsd6RMkjVDRZzb"
    tts_model_id: Optional[str] = "eleven_turbo_v2_5"
    tts_output_format: Optional[str] = "mp3_44100_128"


class RouterResponse(BaseModel):
    missing_fields: List[str] = Field(default_factory=list)
    next_question: Optional[str] = None
    suggested_agents: List[str] = Field(default_factory=list)
    confidence_notes: str = ""
    ready_to_route: bool = False
    session_id: Optional[str] = None
    router_facts: Dict[str, Optional[str]] = Field(default_factory=dict)
    memory_update: str = ""
    mode: Literal["text", "voice"] = "text"
    transcript: Optional[str] = None
    audio_base64: Optional[str] = None
    audio_mime_type: Optional[str] = None


ROUTER_AGENTS = [
    {"id": "vincent_forge", "name": "Vincent Forge"},
    {"id": "katerina_catalyst", "name": "Katerina Catalyst"},
    {"id": "sophia_architect", "name": "Sophia Architect"},
    {"id": "adrian_insight", "name": "Adrian Insight"},
]

ROUTER_AGENT_IDS = {a["id"] for a in ROUTER_AGENTS}
ROUTER_NAME_TO_ID = {a["name"].strip().lower(): a["id"] for a in ROUTER_AGENTS}
ROUTER_ID_TO_NAME = {a["id"]: a["name"] for a in ROUTER_AGENTS}

ROUTER_ALIASES_TO_ID: Dict[str, str] = {
    "vincent": "vincent_forge",
    "forge": "vincent_forge",
    "vincent forge": "vincent_forge",
    "katerina": "katerina_catalyst",
    "catalyst": "katerina_catalyst",
    "katerina catalyst": "katerina_catalyst",
    "sophia": "sophia_architect",
    "architect": "sophia_architect",
    "sophia architect": "sophia_architect",
    "adrian": "adrian_insight",
    "insight": "adrian_insight",
    "adrian insight": "adrian_insight",
}


@dataclass
class RouterSessionState:
    preferred_mentor_id: Optional[str] = None
    current_mentor_id: Optional[str] = None
    accept_count: Dict[str, int] = field(default_factory=dict)
    switch_count: int = 0
    last_seen_ts: float = field(default_factory=lambda: time())
    memory_context: str = ""
    router_facts: Dict[str, Optional[str]] = field(
        default_factory=lambda: {field_name: None for field_name in REQUIRED_ROUTER_FIELDS}
    )
    router_turns: List[Dict[str, str]] = field(default_factory=list)


ROUTER_SESSION_STORE: Dict[str, RouterSessionState] = {}
ROUTER_SESSION_LOCK = threading.Lock()


def get_router_session(session_id: str) -> RouterSessionState:
    sid = (session_id or "").strip() or "default"
    with ROUTER_SESSION_LOCK:
        state = ROUTER_SESSION_STORE.get(sid)
        if not state:
            state = RouterSessionState()
            ROUTER_SESSION_STORE[sid] = state
        state.last_seen_ts = time()
        return state


SYSTEM_PROMPT_FACT_EXTRACTOR = """
You are the Mentorra Router Memory Extractor.

Your job is to update structured routing facts from the user's latest message.

You will receive:
- existing_router_facts
- latest_user_message
- last_question_asked
- founder_profile
- memory_context

Update only fields that are clearly answered or strongly implied.
Do not erase existing facts unless the user explicitly corrects them.
If the latest answer is vague, preserve previous values.

Required fields:
- GOAL: What the founder is trying to achieve. What success looks like.
- MAIN_BARRIER: The main obstacle blocking them right now.
- DOMAIN: Problem category, such as technical, growth, UX, sales, product, fundraising, hiring, strategy, retail, community.
- MENTORSHIP_VALUES: What they value in mentorship, such as accountability, tough love, emotional support, tactical frameworks, industry expertise.
- RISK_PROFILE: Whether they prefer moving fast/taking risks or validating carefully.
- FEEDBACK_STYLE: What feedback helps them most: direct, encouraging, data-driven, story-based, tactical, Socratic.
- RESILIENCE_SIGNAL: How they handle setbacks, rejection, or failure.
- EXPERIENCE_LEVEL: Startup/idea stage, such as idea, pre-seed, seed, growth, scaling, or first-time founder.

Return valid JSON only:

{
  "updated_facts": {
    "GOAL": "string or null",
    "MAIN_BARRIER": "string or null",
    "DOMAIN": "string or null",
    "MENTORSHIP_VALUES": "string or null",
    "RISK_PROFILE": "string or null",
    "FEEDBACK_STYLE": "string or null",
    "RESILIENCE_SIGNAL": "string or null",
    "EXPERIENCE_LEVEL": "string or null"
  },
  "memory_update": "brief summary of what changed",
  "last_answered_field": "one field name or null"
}
"""

SYSTEM_PROMPT_COMPLETENESS_CHECKER = """
You are the Mentorra Router Completeness Checker.

Your job is to inspect accumulated router_facts and ask for the most important missing field.

Return valid JSON only:

{
  "next_question": "string or null",
  "confidence_notes": "brief internal reason"
}

Rules:
- Ask only ONE question.
- Do not ask about fields already filled in router_facts.
- If MAIN_BARRIER is missing, prioritize asking that next.
- If GOAL is missing, ask about the user's goal.
- If all fields are complete, next_question must be null.
"""

SYSTEM_PROMPT_MENTOR_ROUTER = """
You are the Mentorra Mentor Router.

Given complete founder router_facts, choose the best mentor IDs in ranked order.

Valid mentor IDs:
- vincent_forge
- katerina_catalyst
- sophia_architect
- adrian_insight

Mentor matching guide:

vincent_forge:
Best for technical ambition, first-principles thinking, deep tech, hardware, rapid execution, high-risk 10x ideas, blunt feedback.

katerina_catalyst:
Best for bootstrapping, scrappy sales, customer acquisition, resilience, rejection, limited resources, encouragement plus accountability.

sophia_architect:
Best for UX, customer experience, brand, trust, marketplaces, community, emotional product design, thoughtful exploratory feedback.

adrian_insight:
Best for early-stage validation, product-market fit, talking to users, startup fundamentals, pivot decisions, seed-stage strategy.

Return valid JSON only:

{
  "suggested_agents": ["mentor_id", "..."],
  "confidence_notes": "brief explanation of the ranking"
}
"""


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def coerce_track_to_id(track: Optional[str]) -> Optional[str]:
    t = _norm(track)
    if not t:
        return None
    if t in ROUTER_AGENT_IDS:
        return t
    if t in ROUTER_NAME_TO_ID:
        return ROUTER_NAME_TO_ID[t]
    if t in ROUTER_ALIASES_TO_ID:
        return ROUTER_ALIASES_TO_ID[t]
    t2 = re.sub(r"[^a-z0-9_ ]+", "", t).strip()
    if t2 in ROUTER_AGENT_IDS:
        return t2
    if t2 in ROUTER_NAME_TO_ID:
        return ROUTER_NAME_TO_ID[t2]
    if t2 in ROUTER_ALIASES_TO_ID:
        return ROUTER_ALIASES_TO_ID[t2]
    return None


def normalize_suggested_agents(val: Any) -> List[str]:
    if not val:
        return []

    out: List[str] = []
    if isinstance(val, list):
        for item in val:
            if isinstance(item, str):
                mid = coerce_track_to_id(item)
                if mid:
                    out.append(mid)
            elif isinstance(item, dict) and item:
                k = next(iter(item.keys()))
                mid = coerce_track_to_id(str(k))
                if mid:
                    out.append(mid)
    elif isinstance(val, dict):
        for k in val.keys():
            mid = coerce_track_to_id(str(k))
            if mid:
                out.append(mid)

    seen = set()
    deduped: List[str] = []
    for x in out:
        if x in ROUTER_AGENT_IDS and x not in seen:
            seen.add(x)
            deduped.append(x)
    return deduped


def safe_json_loads(content: Optional[str]) -> Dict[str, Any]:
    try:
        return json.loads(content or "{}")
    except json.JSONDecodeError:
        return {}


def call_json_llm(system_prompt: str, user_payload: str, temperature: float = 0.1) -> Dict[str, Any]:
    try:
        completion = openai_client.chat.completions.create(
            model=ROUTER_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_payload},
            ],
            temperature=temperature,
        )
    except APIError:
        completion = openai_client.chat.completions.create(
            model=DEFAULT_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_payload},
            ],
            temperature=temperature,
        )

    return safe_json_loads(completion.choices[0].message.content)


def merge_router_facts(
    existing: Dict[str, Optional[str]],
    updates: Dict[str, Any],
) -> Dict[str, Optional[str]]:
    merged = dict(existing or {})

    for field_name in REQUIRED_ROUTER_FIELDS:
        old_value = merged.get(field_name)
        new_value = updates.get(field_name)

        if isinstance(new_value, str):
            cleaned = new_value.strip()
            if cleaned and cleaned.lower() not in {
                "unknown", "null", "none", "not provided", "n/a",
            }:
                merged[field_name] = cleaned
            else:
                merged[field_name] = old_value
        else:
            merged[field_name] = old_value

    return merged


def is_filled(value: Optional[str]) -> bool:
    if not value:
        return False
    cleaned = value.strip().lower()
    return cleaned not in {"", "unknown", "not provided", "none", "null", "n/a", "unclear"}


def compute_missing_fields(router_facts: Dict[str, Optional[str]]) -> List[str]:
    return [
        field_name
        for field_name in REQUIRED_ROUTER_FIELDS
        if not is_filled(router_facts.get(field_name))
    ]


def run_router(request: UnifiedAssistRequest, effective_user_message: str) -> Dict[str, Any]:
    sid = (request.session_id or "").strip() or "default"
    st = get_router_session(sid)

    active_id = (
        coerce_track_to_id(request.active_mentor_track)
        or st.preferred_mentor_id
        or st.current_mentor_id
    )

    last_question_asked = ""
    for turn in reversed(st.router_turns):
        if turn.get("role") == "assistant":
            last_question_asked = turn.get("content", "")
            break

    st.router_turns.append({"role": "user", "content": effective_user_message})

    extraction_input = json.dumps({
        "existing_router_facts": st.router_facts,
        "latest_user_message": effective_user_message,
        "last_question_asked": last_question_asked,
        "founder_profile": request.founder_profile.model_dump() if request.founder_profile else None,
        "active_mentor_track": request.active_mentor_track or (ROUTER_ID_TO_NAME.get(active_id) if active_id else None),
        "memory_context": request.memory_context or st.memory_context,
    }, indent=2)

    extraction_data = call_json_llm(
        system_prompt=SYSTEM_PROMPT_FACT_EXTRACTOR,
        user_payload=extraction_input,
        temperature=0.1,
    )

    updated_facts = extraction_data.get("updated_facts", {})
    st.router_facts = merge_router_facts(st.router_facts, updated_facts)
    st.memory_context = json.dumps(st.router_facts, indent=2)

    missing_fields = compute_missing_fields(st.router_facts)
    ready_to_route = len(missing_fields) == 0

    next_question = None
    confidence_notes = ""

    if not ready_to_route:
        completeness_input = json.dumps({
            "router_facts": st.router_facts,
            "missing_fields": missing_fields,
            "latest_user_message": effective_user_message,
            "last_question_asked": last_question_asked,
        }, indent=2)

        completeness_data = call_json_llm(
            system_prompt=SYSTEM_PROMPT_COMPLETENESS_CHECKER,
            user_payload=completeness_input,
            temperature=0.1,
        )

        next_question = completeness_data.get("next_question")
        confidence_notes = completeness_data.get("confidence_notes", "")

        if not next_question:
            next_field = missing_fields[0]
            fallback_questions = {
                "GOAL": "What are you trying to achieve with this idea?",
                "MAIN_BARRIER": "What is the biggest obstacle stopping you right now?",
                "DOMAIN": "What area does this problem mostly fall under: product, sales, growth, UX, technical, fundraising, or something else?",
                "MENTORSHIP_VALUES": "What do you value most in a mentor: accountability, tough love, emotional support, tactical frameworks, or industry expertise?",
                "RISK_PROFILE": "Do you prefer moving fast and taking risks, or validating carefully before committing?",
                "FEEDBACK_STYLE": "What type of feedback helps you most: direct, encouraging, data-driven, story-based, tactical, or Socratic?",
                "RESILIENCE_SIGNAL": "How do you usually respond when you face rejection, setbacks, or failure?",
                "EXPERIENCE_LEVEL": "What stage are you at right now: idea, first-time founder, pre-seed, seed, growth, or scaling?",
            }
            next_question = fallback_questions.get(
                next_field,
                "What is the next most important context I should know before matching you with a mentor?",
            )

        st.router_turns.append({"role": "assistant", "content": next_question})

        return {
            "ready_to_route": False,
            "missing_fields": missing_fields,
            "next_question": next_question,
            "suggested_agents": [],
            "confidence_notes": confidence_notes,
            "router_facts": st.router_facts,
            "memory_update": extraction_data.get("memory_update", ""),
            "session_id": sid,
        }

    routing_input = json.dumps({
        "router_facts": st.router_facts,
        "active_mentor_track": request.active_mentor_track or (ROUTER_ID_TO_NAME.get(active_id) if active_id else None),
    }, indent=2)

    routing_data = call_json_llm(
        system_prompt=SYSTEM_PROMPT_MENTOR_ROUTER,
        user_payload=routing_input,
        temperature=0.1,
    )

    suggested_agents = normalize_suggested_agents(routing_data.get("suggested_agents", []))
    confidence_notes = routing_data.get("confidence_notes", "")

    if suggested_agents:
        st.current_mentor_id = suggested_agents[0]

    return {
        "ready_to_route": True,
        "missing_fields": [],
        "next_question": None,
        "suggested_agents": suggested_agents,
        "confidence_notes": confidence_notes,
        "router_facts": st.router_facts,
        "memory_update": extraction_data.get("memory_update", ""),
        "session_id": sid,
    }


# =============================================================================
# MENTOR CHAT — models & roster (multi_agent)
# =============================================================================

MentorId = Literal["vincent_forge", "katerina_catalyst"]
DEFAULT_MENTOR: MentorId = "vincent_forge"

MENTORS: Dict[MentorId, Dict[str, str]] = {
    "vincent_forge": {
        "name": "Vincent Forge",
        "title": "The Impossible Builder",
        "tagline": "Make the impossible inevitable through first principles and relentless execution",
        "voice_id": "JBFqnCBsd6RMkjVDRZzb",
    },
    "katerina_catalyst": {
        "name": "Katerina Catalyst",
        "title": "The Scrappy Disruptor",
        "tagline": "Turn your struggles into your advantage — bootstrap, hustle, believe",
        "voice_id": "cgSgspJ2msm6clMCkdW9",
    },
}

MENTOR_ALIASES_TO_ID: Dict[str, MentorId] = {
    "vincent": "vincent_forge",
    "forge": "vincent_forge",
    "vincent forge": "vincent_forge",
    "vincent_force": "vincent_forge",
    "katerina": "katerina_catalyst",
    "catalyst": "katerina_catalyst",
    "katerina catalyst": "katerina_catalyst",
}

GREETINGS: Dict[MentorId, str] = {
    "vincent_forge": (
        "Hey there, I'm Vincent Forge. Introduce yourself — tell me what you're building "
        "and what's blocking you right now."
    ),
    "katerina_catalyst": (
        "Hey there, I'm Katerina Catalyst. Introduce yourself — tell me what you're working on "
        "and where you're stuck. We'll figure out the scrappy path forward together."
    ),
}


class MultiAgentAssistRequest(BaseModel):
    session_id: Optional[str] = None
    mode: Literal["text", "voice"] = "text"
    mentor_id: Optional[MentorId] = None
    user_message: Optional[str] = None
    audio_base64: Optional[str] = None
    audio_mime_type: Optional[str] = "audio/webm"
    audio_filename: Optional[str] = None
    voice_id: Optional[str] = None
    tts_model_id: Optional[str] = "eleven_turbo_v2_5"
    tts_output_format: Optional[str] = "mp3_44100_128"


class ToolTraceEntry(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    mentor: MentorId = DEFAULT_MENTOR


class MultiAgentResponse(BaseModel):
    session_id: str
    mode: Literal["text", "voice"] = "text"
    reply: str
    active_mentor: MentorId = DEFAULT_MENTOR
    mentor_name: str = "Vincent Forge"
    transcript: Optional[str] = None
    audio_base64: Optional[str] = None
    audio_mime_type: Optional[str] = None
    tool_trace: List[ToolTraceEntry] = Field(default_factory=list)
    switched_mentor: Optional[MentorId] = None


class GreetingResponse(BaseModel):
    mentor_id: MentorId
    mentor_name: str
    reply: str
    audio_base64: Optional[str] = None
    audio_mime_type: Optional[str] = None


SYSTEM_PROMPT_VINCENT_FORGE = """
You are Vincent Forge — The Impossible Builder.

Tagline: Make the impossible inevitable through first principles and relentless execution.

Philosophy:
Most limits are stacked assumptions. If physics allows it, it can be engineered.
Break problems to first principles, aim for 10x breakthroughs, and move fast.
Speed of execution beats perfection. Build things that matter.

Best for:
Moonshots, first-principles problem solving, rapid iteration, scaling hard systems,
technical ambition, deep tech, hardware, high-risk bold bets.

Style:
Direct, intense, impatient with excuses. Cut through noise and push toward action.

Signature question: "What's the actual constraint here?"

Rules:
- Stay in character as Vincent Forge.
- Give concrete, decisive guidance — not generic motivational fluff.
- End with one sharp question or one immediate action for this week when helpful.
- Do not mention you are an AI or a language model.
""".strip()

SYSTEM_PROMPT_KATERINA_CATALYST = """
You are Katerina Catalyst — The Scrappy Disruptor.

Tagline: Turn your struggles into your advantage — bootstrap, hustle, believe.

Philosophy:
Great businesses come from personal pain points. Constraints create creativity.
Start scrappy, sell early, learn from rejection, and turn setbacks into fuel.

Best for:
Bootstrapping, first customers, sales confidence, pricing conversations,
resilience through rejection, limited resources, encouragement plus accountability.

Style:
Warm, encouraging, real — push the founder without shaming them.

Signature question: "What would make YOU buy this?"

Rules:
- Stay in character as Katerina Catalyst.
- Focus on practical next steps the founder can do this week with limited budget.
- Acknowledge emotional reality, then redirect to action.
- Do not mention you are an AI or a language model.
""".strip()

SYSTEM_PROMPTS: Dict[MentorId, str] = {
    "vincent_forge": SYSTEM_PROMPT_VINCENT_FORGE,
    "katerina_catalyst": SYSTEM_PROMPT_KATERINA_CATALYST,
}

TOOL_SWITCH_MENTOR = {
    "type": "function",
    "function": {
        "name": "switch_mentor",
        "description": (
            "Switch the conversation to the other mentor when the user's request "
            "clearly fits the other mentor's strengths better."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mentor_id": {
                    "type": "string",
                    "enum": ["vincent_forge", "katerina_catalyst"],
                    "description": "The mentor to switch to.",
                },
                "reason": {
                    "type": "string",
                    "description": "Brief reason for the switch.",
                },
            },
            "required": ["mentor_id"],
        },
    },
}

TOOLS_BY_MENTOR: Dict[MentorId, List[Dict[str, Any]]] = {
    "vincent_forge": [TOOL_SWITCH_MENTOR],
    "katerina_catalyst": [TOOL_SWITCH_MENTOR],
}


@dataclass
class MentorSessionState:
    active_mentor: MentorId = DEFAULT_MENTOR
    messages: List[Dict[str, Any]] = field(default_factory=list)
    last_seen_ts: float = field(default_factory=lambda: time())


MENTOR_SESSION_STORE: Dict[str, MentorSessionState] = {}
MENTOR_SESSION_LOCK = threading.Lock()


def get_mentor_session(session_id: str) -> MentorSessionState:
    sid = (session_id or "").strip() or "default"
    with MENTOR_SESSION_LOCK:
        state = MENTOR_SESSION_STORE.get(sid)
        if not state:
            state = MentorSessionState()
            MENTOR_SESSION_STORE[sid] = state
        state.last_seen_ts = time()
        return state


def coerce_mentor_id(value: Optional[str]) -> Optional[MentorId]:
    if not value:
        return None
    cleaned = value.strip().lower()
    if cleaned in MENTORS:
        return cleaned  # type: ignore[return-value]
    return MENTOR_ALIASES_TO_ID.get(cleaned)


def extract_explicit_mentor_from_text(text: str) -> Optional[MentorId]:
    msg = (text or "").strip().lower()
    if not msg:
        return None

    for alias, mentor_id in MENTOR_ALIASES_TO_ID.items():
        if re.search(r"\b" + re.escape(alias) + r"\b", msg):
            switch_phrases = [
                "switch", "talk to", "connect me", "use", "give me",
                "i want", "let me speak", "can i get",
            ]
            if any(phrase in msg for phrase in switch_phrases) or msg.strip() in MENTOR_ALIASES_TO_ID:
                return mentor_id
    return None


def resolve_active_mentor(
    session: MentorSessionState,
    request_mentor_id: Optional[MentorId],
    user_message: str,
) -> Tuple[MentorId, Optional[MentorId]]:
    previous = session.active_mentor

    if request_mentor_id:
        session.active_mentor = request_mentor_id
    else:
        explicit = extract_explicit_mentor_from_text(user_message)
        if explicit:
            session.active_mentor = explicit

    switched = previous if session.active_mentor != previous else None
    return session.active_mentor, switched


def message_to_dict(message: Any) -> Dict[str, Any]:
    if hasattr(message, "model_dump"):
        return message.model_dump(exclude_none=True)
    return dict(message)


def mentor_display_name(mentor_id: MentorId) -> str:
    return MENTORS[mentor_id]["name"]


def default_voice_for_mentor(mentor_id: MentorId) -> str:
    return MENTORS[mentor_id]["voice_id"]


def execute_switch_mentor(
    session: MentorSessionState,
    mentor_id: str,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    target = coerce_mentor_id(mentor_id)
    if not target:
        return {"error": f"Unknown mentor_id: {mentor_id}"}

    previous = session.active_mentor
    session.active_mentor = target

    return {
        "switched_from": previous,
        "switched_to": target,
        "mentor_name": mentor_display_name(target),
        "reason": reason or "",
    }


def execute_tool_call(
    session: MentorSessionState,
    tool_name: str,
    arguments: Dict[str, Any],
    trace: List[ToolTraceEntry],
) -> Any:
    mentor = session.active_mentor

    if tool_name == "switch_mentor":
        result = execute_switch_mentor(
            session=session,
            mentor_id=str(arguments.get("mentor_id", "")),
            reason=arguments.get("reason"),
        )
    else:
        result = {"error": f"Unknown tool: {tool_name}"}

    trace.append(
        ToolTraceEntry(
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            mentor=mentor,
        )
    )
    return result


def run_mentor_turn(session: MentorSessionState, user_message: str) -> Dict[str, Any]:
    session.messages.append({"role": "user", "content": user_message})

    trace: List[ToolTraceEntry] = []
    switched_mentor: Optional[MentorId] = None

    for _ in range(MAX_TOOL_ITERATIONS):
        mentor = session.active_mentor
        tools = TOOLS_BY_MENTOR.get(mentor) or None

        request_kwargs: Dict[str, Any] = {
            "model": DEFAULT_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPTS[mentor]},
                *session.messages,
            ],
        }
        if tools:
            request_kwargs["tools"] = tools
            request_kwargs["tool_choice"] = "auto"

        try:
            completion = openai_client.chat.completions.create(**request_kwargs)
        except APIError as exc:
            raise HTTPException(status_code=502, detail=f"OpenAI API error: {exc}") from exc

        assistant_message = completion.choices[0].message
        session.messages.append(message_to_dict(assistant_message))

        if assistant_message.tool_calls:
            for tool_call in assistant_message.tool_calls:
                fn = tool_call.function
                args = json.loads(fn.arguments or "{}")
                result = execute_tool_call(session, fn.name, args, trace)

                if fn.name == "switch_mentor" and isinstance(result, dict):
                    switched_mentor = result.get("switched_to")

                session.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result),
                    }
                )
            continue

        reply = (assistant_message.content or "").strip()
        if not reply:
            reply = f"{mentor_display_name(mentor)} here — what are you building?"

        return {
            "reply": reply,
            "active_mentor": session.active_mentor,
            "tool_trace": trace,
            "switched_mentor": switched_mentor,
        }

    raise HTTPException(
        status_code=500,
        detail=f"Mentor loop exceeded {MAX_TOOL_ITERATIONS} tool iterations",
    )


def process_mentor_assist_request(
    request: MultiAgentAssistRequest,
    effective_user_message: str,
) -> MultiAgentResponse:
    sid = (request.session_id or "").strip() or "default"
    session = get_mentor_session(sid)

    _, explicit_switch = resolve_active_mentor(
        session=session,
        request_mentor_id=request.mentor_id,
        user_message=effective_user_message,
    )

    result = run_mentor_turn(session, effective_user_message)

    switched = result.get("switched_mentor") or explicit_switch
    active = result["active_mentor"]

    audio_base64 = None
    audio_mime_type = None
    if request.mode == "voice" and result["reply"]:
        voice_id = request.voice_id or default_voice_for_mentor(active)
        audio_base64, audio_mime_type = synthesize_text_to_base64_audio(
            text=result["reply"],
            voice_id=voice_id,
            model_id=request.tts_model_id or "eleven_turbo_v2_5",
            output_format=request.tts_output_format or "mp3_44100_128",
        )

    return MultiAgentResponse(
        session_id=sid,
        mode=request.mode,
        reply=result["reply"],
        active_mentor=active,
        mentor_name=mentor_display_name(active),
        tool_trace=result["tool_trace"],
        switched_mentor=switched,
        audio_base64=audio_base64,
        audio_mime_type=audio_mime_type,
    )


# =============================================================================
# Shared audio helpers
# =============================================================================


def decode_audio_to_bytes(audio_base64: str) -> bytes:
    try:
        if "," in audio_base64 and audio_base64.strip().startswith("data:"):
            audio_base64 = audio_base64.split(",", 1)[1]
        return base64.b64decode(audio_base64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64 audio payload: {exc}")


def guess_audio_filename(mime_type: Optional[str], filename: Optional[str]) -> str:
    if filename:
        return filename
    mapping = {
        "audio/webm": "audio.webm",
        "audio/wav": "audio.wav",
        "audio/x-wav": "audio.wav",
        "audio/mpeg": "audio.mp3",
        "audio/mp3": "audio.mp3",
        "audio/mp4": "audio.mp4",
        "audio/aac": "audio.aac",
        "audio/ogg": "audio.ogg",
    }
    return mapping.get((mime_type or "").lower(), "audio/webm")


def transcribe_audio_bytes_with_openai(audio_bytes: bytes, filename: str) -> str:
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename
    transcript = openai_client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
    )
    return transcript.text


def synthesize_text_to_base64_audio(
    text: str,
    voice_id: str,
    model_id: str,
    output_format: str,
) -> Tuple[str, str]:
    audio_stream = elevenlabs_client.text_to_speech.convert(
        voice_id=voice_id,
        model_id=model_id,
        text=text,
        output_format=output_format,
    )
    audio_bytes = b"".join(chunk for chunk in audio_stream if chunk)

    mime_type = "audio/mpeg"
    if output_format.startswith("pcm"):
        mime_type = "audio/wav"

    return base64.b64encode(audio_bytes).decode("utf-8"), mime_type


def resolve_effective_user_message(
    user_message: Optional[str],
    mode: str,
    audio_base64: Optional[str],
    audio_mime_type: Optional[str],
    audio_filename: Optional[str],
) -> Tuple[str, Optional[str]]:
    transcript: Optional[str] = None
    effective = (user_message or "").strip()

    if mode == "voice":
        if not audio_base64:
            raise HTTPException(status_code=400, detail="audio_base64 is required when mode='voice'.")
        audio_bytes = decode_audio_to_bytes(audio_base64)
        filename = guess_audio_filename(audio_mime_type, audio_filename)
        transcript = transcribe_audio_bytes_with_openai(audio_bytes, filename)
        effective = transcript.strip()

    if not effective:
        raise HTTPException(
            status_code=400,
            detail="user_message is required for text mode, or provide transcribable audio for voice mode.",
        )

    return effective, transcript


# =============================================================================
# Handlers
# =============================================================================


async def handle_router_assist(request: UnifiedAssistRequest) -> RouterResponse:
    effective_user_message, transcript = resolve_effective_user_message(
        request.user_message,
        request.mode,
        request.audio_base64,
        request.audio_mime_type,
        request.audio_filename,
    )

    data = run_router(request, effective_user_message)

    audio_base64 = None
    audio_mime_type = None
    if request.mode == "voice" and data.get("next_question"):
        audio_base64, audio_mime_type = synthesize_text_to_base64_audio(
            text=data["next_question"],
            voice_id=request.voice_id or "JBFqnCBsd6RMkjVDRZzb",
            model_id=request.tts_model_id or "eleven_turbo_v2_5",
            output_format=request.tts_output_format or "mp3_44100_128",
        )

    return RouterResponse(
        **data,
        mode=request.mode,
        transcript=transcript,
        audio_base64=audio_base64,
        audio_mime_type=audio_mime_type,
    )


async def handle_mentor_assist(request: MultiAgentAssistRequest) -> MultiAgentResponse:
    effective_user_message, transcript = resolve_effective_user_message(
        request.user_message,
        request.mode,
        request.audio_base64,
        request.audio_mime_type,
        request.audio_filename,
    )

    response = process_mentor_assist_request(request, effective_user_message)
    response.transcript = transcript
    return response


def is_mentor_chat_request(body: Dict[str, Any]) -> bool:
    """Route to mentor chat when mentor_id is present."""
    mentor_id = body.get("mentor_id")
    return mentor_id is not None and str(mentor_id).strip() != ""


# =============================================================================
# FastAPI endpoints
# =============================================================================


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "mentorra-agents",
        "router_agents": [a["id"] for a in ROUTER_AGENTS],
        "chat_mentors": list(MENTORS.keys()),
    }


@app.get("/api/mentors")
def list_mentors():
    return [{"id": mentor_id, **meta} for mentor_id, meta in MENTORS.items()]


@app.get("/api/greeting", response_model=GreetingResponse)
async def greeting(mentor_id: MentorId = DEFAULT_MENTOR):
    try:
        text = GREETINGS[mentor_id]
        voice_id = default_voice_for_mentor(mentor_id)
        audio_base64, audio_mime_type = synthesize_text_to_base64_audio(
            text=text,
            voice_id=voice_id,
            model_id="eleven_turbo_v2_5",
            output_format="mp3_44100_128",
        )
        return GreetingResponse(
            mentor_id=mentor_id,
            mentor_name=mentor_display_name(mentor_id),
            reply=text,
            audio_base64=audio_base64,
            audio_mime_type=audio_mime_type,
        )
    except Exception as exc:
        print(f"Greeting Error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/session/{session_id}")
def get_mentor_session_debug(session_id: str):
    session = get_mentor_session(session_id)
    return {
        "session_id": session_id,
        "active_mentor": session.active_mentor,
        "mentor_name": mentor_display_name(session.active_mentor),
        "message_count": len(session.messages),
        "messages": session.messages,
    }


@app.get("/api/router-session/{session_id}")
def get_router_session_debug(session_id: str):
    session = get_router_session(session_id)
    return {
        "session_id": session_id,
        "router_facts": session.router_facts,
        "current_mentor_id": session.current_mentor_id,
        "message_count": len(session.router_turns),
        "router_turns": session.router_turns,
    }


@app.post("/api/assist")
async def assist(request: Request) -> Union[RouterResponse, MultiAgentResponse]:
    """
    Unified assist endpoint.
    - Requests with mentor_id → 1-on-1 mentor chat
    - All other requests → boardroom router intake
    """
    try:
        body = await request.json()
        if is_mentor_chat_request(body):
            return await handle_mentor_assist(MultiAgentAssistRequest(**body))
        return await handle_router_assist(UnifiedAssistRequest(**body))
    except HTTPException:
        raise
    except Exception as exc:
        print(f"Assist Error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/mentor-chat", response_model=MultiAgentResponse)
async def mentor_chat(request: MultiAgentAssistRequest):
    """Explicit mentor chat endpoint (same handler as /api/assist with mentor_id)."""
    try:
        return await handle_mentor_assist(request)
    except HTTPException:
        raise
    except Exception as exc:
        print(f"Mentor Chat Error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/mentor-assist", response_model=RouterResponse)
async def mentor_assist_compat(request: UnifiedAssistRequest):
    request.mode = "text"
    return await handle_router_assist(request)


@app.post("/api/voice/speak")
async def text_to_speech_stream(
    text: str,
    voice_id: str = "JBFqnCBsd6RMkjVDRZzb",
    model_id: str = "eleven_turbo_v2_5",
    output_format: str = "mp3_44100_128",
):
    try:
        audio_stream = elevenlabs_client.text_to_speech.convert(
            voice_id=voice_id,
            model_id=model_id,
            text=text,
            output_format=output_format,
        )

        def iterfile():
            for chunk in audio_stream:
                if chunk:
                    yield chunk

        return StreamingResponse(iterfile(), media_type="audio/mpeg")
    except Exception as exc:
        print(f"TTS Error: {exc}")
        raise HTTPException(status_code=500, detail=f"Text-to-speech failed: {exc}") from exc


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
