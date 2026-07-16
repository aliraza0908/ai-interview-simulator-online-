"""
utils/evaluator_gemini.py — Evaluate interview answers using Groq (Llama 3).
Returns score (0-10), feedback, and missing_keywords for each Q&A pair.

Persona- and interview-type-aware: feedback tone matches the interviewer persona
(strict HR vs friendly tech lead) and the scoring rubric matches the interview type
(behavioral vs technical vs system design vs case study). See utils/personas.py.
"""

import json
import streamlit as st
from groq import Groq
from config import GROQ_API_KEY, LLM_MODEL
from utils.personas import (
    get_persona,
    get_interview_type,
    panel_sub_persona,
    DEFAULT_PERSONA_KEY,
    DEFAULT_INTERVIEW_TYPE_KEY,
)
from utils.confidence_analyzer import summarize_for_prompt


def evaluate_answer(
    question: str,
    answer: str,
    persona_key: str = DEFAULT_PERSONA_KEY,
    interview_type_key: str = DEFAULT_INTERVIEW_TYPE_KEY,
    delivery_context: str = None,
) -> dict:
    """
    Evaluate a single Q&A pair with Groq, in the voice/rubric of the chosen persona + interview type.
    delivery_context: optional short string describing automated delivery/confidence signals
        (speaking pace, filler words, eye contact) so the written feedback can reference them.
    Returns dict: {score: int, feedback: str, missing_keywords: list}
    On failure, returns a default low-score result rather than crashing.
    """
    if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
        return {"score": 0, "feedback": "Groq API key not configured.", "missing_keywords": []}

    persona = get_persona(persona_key)
    itype = get_interview_type(interview_type_key)

    # Groq Client Initialize kiya
    client = Groq(api_key=GROQ_API_KEY)

    delivery_block = ""
    if delivery_context:
        delivery_block = (
            f"\nAutomated delivery data for this answer (computed, not your judgment — you may "
            f"briefly reference it in your feedback, but base the SCORE mainly on content): "
            f"{delivery_context}\n"
        )

    prompt = f"""You are evaluating a candidate's interview answer.

INTERVIEWER PERSONA (write feedback in this voice/tone):
{persona['eval_style']}

INTERVIEW TYPE (use this scoring focus):
{itype['eval_focus']}

Question: {question}

Candidate's Answer: {answer}
{delivery_block}
Evaluate the answer and respond with ONLY a valid JSON object (no markdown, no fences, no extra text):
{{
  "score": <integer 0-10>,
  "feedback": "<1-2 sentence constructive feedback, written in the persona's voice/tone>",
  "missing_keywords": ["<keyword1>", "<keyword2>"]
}}

Scoring guide:
- 9-10: Excellent, comprehensive, shows deep understanding
- 7-8: Good answer, covers main points with minor gaps
- 5-6: Adequate but missing important aspects
- 3-4: Partial answer, significant gaps
- 1-2: Very poor, mostly off-topic or incorrect
- 0: No answer or completely irrelevant

missing_keywords: List 2-5 important terms/concepts the candidate should have mentioned but didn't. Empty list if the answer was comprehensive.

Respond with ONLY the JSON object:"""

    try:
        # Groq chat completion format
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Low temperature taake evaluation strictly deterministic ho
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            lines = raw.split("\n")
            if lines[-1].strip() == "```":
                raw = "\n".join(lines[1:-1])
            else:
                raw = "\n".join(lines[1:])
            raw = raw.strip()

        result = json.loads(raw)

        # Validate and sanitize
        score = max(0, min(10, int(result.get("score", 0))))
        feedback = str(result.get("feedback", "")).strip()
        missing_kw = result.get("missing_keywords", [])
        if not isinstance(missing_kw, list):
            missing_kw = []

        return {"score": score, "feedback": feedback, "missing_keywords": missing_kw}

    except json.JSONDecodeError:
        return {"score": 3, "feedback": "Could not parse evaluation from Groq. Please review this answer manually.", "missing_keywords": []}
    except Exception as e:
        return {"score": 3, "feedback": f"Evaluation error: {e}", "missing_keywords": []}


def evaluate_all_answers(
    qa_pairs: list,
    persona_key: str = DEFAULT_PERSONA_KEY,
    interview_type_key: str = DEFAULT_INTERVIEW_TYPE_KEY,
) -> list:
    """
    Evaluate all Q&A pairs.
    qa_pairs: list of dicts with 'question' and 'answer' keys, and optionally
        'confidence_metrics' (from utils.webcam_capture, when webcam recording was used).
    In "panel" persona mode, each question is evaluated in the voice of whichever
    panelist (Sarah/HR or Alex/Tech) would have asked it, alternating by index —
    matching how the questions were generated.
    Returns list of dicts with evaluation results merged in (including confidence_score
    and delivery notes, when available).
    """
    results = []
    for i, pair in enumerate(qa_pairs):
        eval_persona_key = persona_key
        if persona_key == "panel":
            eval_persona_key = panel_sub_persona(i)["key"]

        confidence = pair.get("confidence_metrics")
        delivery_context = summarize_for_prompt(confidence) if confidence else None

        with st.spinner(f"Evaluating answer {i + 1} of {len(qa_pairs)}..."):
            eval_result = evaluate_answer(
                pair["question"],
                pair.get("answer", ""),
                persona_key=eval_persona_key,
                interview_type_key=interview_type_key,
                delivery_context=delivery_context,
            )

        result = {
            "question_number": i + 1,
            "question_text": pair["question"],
            "answer_text": pair.get("answer", ""),
            **eval_result,
        }
        if confidence:
            result["confidence_score"] = confidence.get("confidence_score")
            result["delivery_notes"] = confidence.get("notes", [])
            result["wpm"] = confidence.get("wpm")
            result["eye_contact_pct"] = confidence.get("eye_contact_pct")
        results.append(result)
    return results