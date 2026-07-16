"""
utils/question_generator.py — Generate personalized interview questions from CV text using Groq.

Supports persona-aware and interview-type-aware generation (see utils/personas.py):
  - persona controls the INTERVIEWER'S VOICE/STYLE (formal HR vs friendly tech vs panel)
  - interview_type controls WHAT KIND of questions get asked (HR / technical / system design /
    case study / mixed)
"""

import json
import streamlit as st
from groq import Groq
from config import GROQ_API_KEY, LLM_MODEL
from utils.personas import get_persona, get_interview_type, DEFAULT_PERSONA_KEY, DEFAULT_INTERVIEW_TYPE_KEY


def generate_questions_from_cv(
    cv_text: str,
    num_questions: int = 8,
    persona_key: str = DEFAULT_PERSONA_KEY,
    interview_type_key: str = DEFAULT_INTERVIEW_TYPE_KEY,
) -> list[str]:
    """
    Send CV text to Groq and get back a list of personalized interview questions,
    shaped by the chosen interviewer persona and interview type.
    Returns a list of question strings.
    Raises on failure — caller should handle with st.error.
    """
    if not cv_text or len(cv_text.strip()) < 50:
        st.warning("⚠️ CV text is too short to generate meaningful questions.")
        raise ValueError("CV text too short.")

    persona = get_persona(persona_key)
    itype = get_interview_type(interview_type_key)

    # Groq Client Initialize kiya
    client = Groq(api_key=GROQ_API_KEY)

    prompt = f"""You are an experienced interviewer. A candidate has submitted their CV/resume below.

INTERVIEWER PERSONA (this shapes tone and phrasing of the questions you write):
{persona['question_style']}

INTERVIEW TYPE (this shapes WHAT KIND of questions to ask):
{itype['prompt_focus']}

Your task: Generate exactly {num_questions} interview questions tailored specifically to THIS candidate's background, following both the persona tone and the interview type focus above.

Rules:
- Base questions on the candidate's ACTUAL skills, technologies, projects, and experience listed in the CV.
- Do NOT ask generic questions — make each question specific to something in their CV.
- Stay consistent with the interviewer persona's tone and the interview type's focus described above.
- Respond with ONLY a valid JSON array of strings. No markdown, no code fences, no explanation, no numbering. Just the raw JSON array.

Example format:
["Question 1 here?", "Question 2 here?", "Question 3 here?"]

CV Content:
---
{cv_text}
---

Respond with ONLY the JSON array of {num_questions} questions:"""

    try:
        # Groq chat completion format
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown fences if Groq added them despite instructions
        if raw.startswith("```"):
            lines = raw.split("\n")
            if lines[-1].strip() == "```":
                raw = "\n".join(lines[1:-1])
            else:
                raw = "\n".join(lines[1:])
            raw = raw.strip()

        questions = json.loads(raw)

        if not isinstance(questions, list) or len(questions) == 0:
            raise ValueError("Groq returned an unexpected format.")

        # Ensure all items are strings
        questions = [str(q).strip() for q in questions if str(q).strip()]
        return questions

    except json.JSONDecodeError as e:
        st.error(f"❌ Failed to parse questions from Groq. Please try re-uploading your CV. (Detail: {e})")
        raise
    except Exception as e:
        st.error(f"❌ Question generation failed: {e}")
        raise