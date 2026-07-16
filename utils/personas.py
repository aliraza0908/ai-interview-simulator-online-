"""
utils/personas.py — Interviewer personas, interview types, and timer modes.

This module is the single source of truth for "realism" features:
  - PERSONAS: who is interviewing you (tone, voice accent, question style)
  - INTERVIEW_TYPES: what kind of round it is (HR / Technical / System Design / Case Study / Mixed)
  - TIMER_MODES: how much pressure the candidate is under per question

Nothing here talks to an LLM or to Streamlit — it's pure config + small helpers,
so question_generator.py, evaluator_gemini.py, tts.py, and interview_page.py
can all import from one place without circular imports.
"""

import random

# ────────────────────────────────────────────────────────────
# INTERVIEWER PERSONAS
# ────────────────────────────────────────────────────────────
# tts_tld controls the gTTS accent (gTTS has no distinct "voices", but the
# Google Translate TLD changes the accent enough to feel like a different
# speaker — com=US, co.uk=British, com.au=Australian, co.in=Indian English).

PERSONAS = {
    "strict_hr": {
        "key": "strict_hr",
        "name": "Ms. Sarah Whitfield",
        "title": "Senior HR Manager",
        "avatar": "👔",
        "tagline": "Formal, direct, no small talk. Wants precise, structured answers.",
        "tts_tld": "co.uk",
        "question_style": (
            "Adopt the voice of a formal, no-nonsense Senior HR Manager named Sarah Whitfield. "
            "You are direct and slightly demanding. You care about professionalism, ownership, "
            "conflict handling, and whether the candidate can back up claims with specifics. "
            "Do not be unkind, but do not soften questions — ask them plainly and expect rigor."
        ),
        "eval_style": (
            "Evaluate as a strict, formal HR Manager would: reward structured, specific, "
            "ownership-driven answers (e.g. STAR method) and penalize vague or rambling ones. "
            "Keep feedback brief, professional, and a little blunt — no excessive praise."
        ),
        "intro_line": (
            "Good day. I'm Sarah Whitfield, Senior HR Manager. We'll go through a series of "
            "questions — please answer clearly and concisely."
        ),
    },
    "friendly_tech": {
        "key": "friendly_tech",
        "name": "Alex Chen",
        "title": "Friendly Tech Lead",
        "avatar": "🧑‍💻",
        "tagline": "Warm, curious, loves digging into how you actually built things.",
        "tts_tld": "com",
        "question_style": (
            "Adopt the voice of a warm, encouraging Tech Lead named Alex Chen. You're genuinely "
            "curious about how the candidate thinks and built things, you ask natural follow-up-style "
            "questions about their real projects/skills, and you keep the tone conversational and "
            "low-pressure, like a friendly 1:1 chat rather than an interrogation."
        ),
        "eval_style": (
            "Evaluate as a friendly, encouraging Tech Lead would: still be honest about gaps, but "
            "frame feedback constructively and highlight what the candidate did well before pointing "
            "out what's missing."
        ),
        "intro_line": (
            "Hey! I'm Alex, I lead the engineering team here. No pressure — let's just talk through "
            "your background and experience."
        ),
    },
    "panel": {
        "key": "panel",
        "name": "Panel Interview",
        "title": "Sarah Whitfield (HR) + Alex Chen (Tech Lead)",
        "avatar": "🧑‍⚖️🧑‍💻",
        "tagline": "Two interviewers alternate questions — the most realistic format.",
        "tts_tld": "com",  # overridden per-question in panel mode
        "question_style": (
            "You are generating questions for a TWO-PERSON PANEL interview: Sarah Whitfield "
            "(formal Senior HR Manager, focuses on behavioral/ownership/conflict questions) and "
            "Alex Chen (friendly Tech Lead, focuses on technical depth and real project specifics). "
            "Alternate the questions so roughly half feel like Sarah would ask them (formal, "
            "behavioral) and half feel like Alex would ask them (curious, technical, conversational)."
        ),
        "eval_style": (
            "Evaluate fairly and professionally, considering both a formal HR lens (structure, "
            "ownership, communication) and a technical lens (correctness, depth, specificity), "
            "whichever is more relevant to the individual question."
        ),
        "intro_line": (
            "Hi, thanks for joining. I'm Sarah from HR, and this is Alex, our Tech Lead — we'll "
            "be alternating questions today."
        ),
    },
}

DEFAULT_PERSONA_KEY = "friendly_tech"


def get_persona(key: str) -> dict:
    return PERSONAS.get(key, PERSONAS[DEFAULT_PERSONA_KEY])


def panel_sub_persona(question_index: int) -> dict:
    """
    In panel mode, alternate between the two underlying personas by question index.
    Even index -> Sarah (HR), odd index -> Alex (Tech).
    """
    return PERSONAS["strict_hr"] if question_index % 2 == 0 else PERSONAS["friendly_tech"]


# ────────────────────────────────────────────────────────────
# INTERVIEW TYPES
# ────────────────────────────────────────────────────────────

INTERVIEW_TYPES = {
    "mixed": {
        "key": "mixed",
        "label": "Mixed — Full Simulation",
        "icon": "🎯",
        "description": "A realistic blend of behavioral, technical, and scenario questions.",
        "prompt_focus": (
            "Generate a balanced MIX of question types: roughly a third behavioral/HR "
            "(teamwork, ownership, challenges), a third technical (specific to the candidate's "
            "listed skills/projects), and a third scenario or problem-solving questions."
        ),
        "eval_focus": "Use a balanced rubric appropriate to whatever each individual question is testing.",
    },
    "hr": {
        "key": "hr",
        "label": "HR / Behavioral Round",
        "icon": "🤝",
        "description": "Soft skills, motivation, teamwork, conflict resolution.",
        "prompt_focus": (
            "Generate ONLY behavioral/HR-style questions: motivation, teamwork, conflict handling, "
            "ownership, career goals, and how the candidate's experience shows soft skills. "
            "Reference specifics from their CV (companies, roles, durations) where relevant, but do "
            "NOT ask deep technical/coding questions."
        ),
        "eval_focus": (
            "Score primarily on structure (ideally STAR: Situation, Task, Action, Result), "
            "self-awareness, and communication clarity rather than technical correctness."
        ),
    },
    "technical": {
        "key": "technical",
        "label": "Technical Round",
        "icon": "💻",
        "description": "Deep dive into the candidate's actual skills, tools, and projects.",
        "prompt_focus": (
            "Generate ONLY technical questions that probe deeply into the specific technologies, "
            "tools, frameworks, and projects explicitly listed in the candidate's CV. Ask 'how' and "
            "'why' questions (architecture choices, trade-offs, debugging, optimization) rather than "
            "generic definitions."
        ),
        "eval_focus": (
            "Score primarily on technical correctness, depth, and specificity. Vague or textbook-only "
            "answers without concrete detail should score lower even if technically not wrong."
        ),
    },
    "system_design": {
        "key": "system_design",
        "label": "System Design Round",
        "icon": "🏗️",
        "description": "Architecture, scalability, and trade-off thinking (best for senior/tech roles).",
        "prompt_focus": (
            "Generate system-design / architecture-style questions inspired by the seniority and "
            "domain implied by the candidate's CV (e.g. design a system related to the kind of "
            "products/companies they've worked on). Focus on scalability, trade-offs, data modeling, "
            "and reliability rather than syntax-level coding."
        ),
        "eval_focus": (
            "Score on structured thinking, awareness of trade-offs (e.g. consistency vs availability, "
            "cost vs performance), and whether the candidate considered scale and failure modes — "
            "not on whether they reached one 'correct' design."
        ),
    },
    "case_study": {
        "key": "case_study",
        "label": "Case Study / Problem-Solving",
        "icon": "🧩",
        "description": "Open-ended scenarios that test structured problem-solving.",
        "prompt_focus": (
            "Generate open-ended scenario/case-study questions relevant to the candidate's field "
            "(e.g. 'how would you handle X situation', 'a project is failing because of Y, what do "
            "you do'). Ground scenarios loosely in the kind of role/industry their CV suggests."
        ),
        "eval_focus": (
            "Score on structured problem-solving: did they clarify assumptions, break the problem "
            "down logically, and justify their reasoning — not just whether they landed on 'an' answer."
        ),
    },
}

DEFAULT_INTERVIEW_TYPE_KEY = "mixed"


def get_interview_type(key: str) -> dict:
    return INTERVIEW_TYPES.get(key, INTERVIEW_TYPES[DEFAULT_INTERVIEW_TYPE_KEY])


# ────────────────────────────────────────────────────────────
# TIMER / PRESSURE MODES
# ────────────────────────────────────────────────────────────

TIMER_MODES = {
    "off": {"key": "off", "label": "Off — No Timer", "seconds": None, "auto_skip": False},
    "relaxed": {"key": "relaxed", "label": "Relaxed — 3 min/question", "seconds": 180, "auto_skip": False},
    "standard": {"key": "standard", "label": "Standard — 90 sec/question", "seconds": 90, "auto_skip": False},
    "strict": {"key": "strict", "label": "Strict — 45 sec/question (auto-skip)", "seconds": 45, "auto_skip": True},
}

DEFAULT_TIMER_KEY = "off"


def get_timer_mode(key: str) -> dict:
    return TIMER_MODES.get(key, TIMER_MODES[DEFAULT_TIMER_KEY])
