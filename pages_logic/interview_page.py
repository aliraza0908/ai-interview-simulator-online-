"""
pages_logic/interview_page.py — Turn-based voice interview loop.
Interviewer (persona) speaks question → user records → transcribe → confirm → next question.

Realism features:
  - Interviewer persona shown per question (avatar/name), with panel mode alternating
    between two interviewers question-by-question.
  - Optional countdown timer per question (relaxed / standard / strict pressure modes),
    with auto-skip in strict mode.
"""

import time
import streamlit as st
from utils.tts import text_to_speech
from utils.stt_assembly import transcribe_audio, TranscriptionError
from utils.webcam_capture import render_webcam_recorder, webcam_available
from utils.personas import (
    get_persona,
    get_interview_type,
    get_timer_mode,
    panel_sub_persona,
    DEFAULT_PERSONA_KEY,
    DEFAULT_INTERVIEW_TYPE_KEY,
    DEFAULT_TIMER_KEY,
)

try:
    from streamlit_autorefresh import st_autorefresh
    _HAS_AUTOREFRESH = True
except ImportError:
    _HAS_AUTOREFRESH = False


def _active_persona(idx: int) -> dict:
    """Resolve which persona is 'asking' this question (handles panel mode)."""
    persona_key = st.session_state.get("persona_key", DEFAULT_PERSONA_KEY)
    if persona_key == "panel":
        return panel_sub_persona(idx)
    return get_persona(persona_key)


def _render_timer(idx: int, already_recorded: bool) -> bool:
    """
    Render the countdown timer (if enabled) for the current question.
    Returns True if time has expired AND auto-skip should happen.
    """
    timer_mode = get_timer_mode(st.session_state.get("timer_key", DEFAULT_TIMER_KEY))
    seconds = timer_mode["seconds"]
    if seconds is None or already_recorded:
        return False  # timer off, or candidate already recorded — stop counting

    start_key = f"q_start_time_{idx}"
    if start_key not in st.session_state:
        st.session_state[start_key] = time.time()

    elapsed = time.time() - st.session_state[start_key]
    remaining = max(0, seconds - elapsed)
    fraction = remaining / seconds if seconds else 0

    if remaining > 0 and _HAS_AUTOREFRESH:
        st_autorefresh(interval=1000, key=f"timer_refresh_{idx}", limit=seconds + 2)

    color = "#16a34a" if fraction > 0.5 else "#d97706" if fraction > 0.2 else "#dc2626"
    mins, secs = divmod(int(remaining), 60)
    st.markdown(
        f"""
        <div style='text-align:center; margin:0.3rem 0 0.6rem 0;'>
            <span style='font-size:1.3rem; font-weight:700; color:{color};'>
                ⏱️ {mins:01d}:{secs:02d}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.progress(fraction, text=None)

    if remaining <= 0:
        if timer_mode["auto_skip"]:
            return True
        st.warning("⏰ Time's up — answer when you're ready, but try to keep it tight.")
    return False


def render():
    questions = st.session_state.get("questions", [])
    idx = st.session_state.get("current_q_index", 0)
    total = len(questions)

    if idx >= total:
        # All questions answered — move to evaluation
        st.session_state.app_stage = "evaluating"
        st.rerun()
        return

    question = questions[idx]
    persona = _active_persona(idx)
    itype = get_interview_type(st.session_state.get("interview_type_key", DEFAULT_INTERVIEW_TYPE_KEY))

    # ── Interviewer + round badge ───────────────────────────
    st.markdown(
        f"""
        <div style='text-align:center; margin-bottom:0.3rem;'>
            <span style='background:#eff6ff; color:#1e40af; padding:0.2rem 0.7rem;
                         border-radius:999px; font-size:0.78rem; font-weight:600;'>
                {itype['icon']} {itype['label']}
            </span>
        </div>
        <div style='text-align:center; margin-bottom:0.5rem;'>
            <span style='font-size:1.4rem;'>{persona['avatar']}</span>
            <span style='color:#334155; font-size:0.92rem; font-weight:600;'> {persona['name']}</span>
            <span style='color:#94a3b8; font-size:0.85rem;'> · {persona['title']}</span>
        </div>
        <div style='text-align:center; margin-bottom:0.5rem;'>
            <span style='color:#64748b; font-size:0.9rem;'>Question {idx + 1} of {total}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.progress((idx) / total, text="Interview Progress")

    # ── Question card ──────────────────────────────────────
    with st.container(border=True):
        st.markdown(
            f"""
            <div style='background:linear-gradient(135deg,#eff6ff,#dbeafe);
                        padding:1.2rem 1.5rem; border-radius:10px; margin-bottom:0.5rem;'>
                <p style='color:#1e3a8a; font-size:0.85rem; margin:0 0 0.4rem 0;
                           font-weight:600; text-transform:uppercase; letter-spacing:.05em;'>
                    🎤 Question {idx + 1}
                </p>
                <p style='color:#1e293b; font-size:1.1rem; margin:0; font-weight:500;'>
                    {question}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # TTS — auto-play the question, in this persona's accent.
        # On the very first question, prepend the persona's spoken intro line.
        tts_key = f"tts_played_{idx}"
        if tts_key not in st.session_state:
            speak_text = question
            if idx == 0:
                intro_persona = get_persona(st.session_state.get("persona_key", DEFAULT_PERSONA_KEY))
                speak_text = f"{intro_persona['intro_line']} ... {question}"
            audio_bytes = text_to_speech(speak_text, tld=persona.get("tts_tld", "com"))
            st.session_state[tts_key] = audio_bytes

        audio_bytes = st.session_state.get(tts_key)
        if audio_bytes:
            st.audio(audio_bytes, format="audio/mp3", autoplay=True)
        else:
            # TTS failed — already warned in tts.py — show manual play button if we retry
            if st.button("🔊 Retry Audio", key=f"retry_tts_{idx}"):
                audio_bytes = text_to_speech(question, tld=persona.get("tts_tld", "com"))
                if audio_bytes:
                    st.session_state[tts_key] = audio_bytes
                    st.rerun()

    # ── Recording section ──────────────────────────────────
    use_webcam = webcam_available()
    transcript_key = f"transcript_{idx}"

    if use_webcam:
        render_webcam_recorder(idx)  # populates transcript_{idx} + confidence_{idx} when done
        # "Already recording" for timer purposes = webcam session has started, or already finalized
        already_recorded = (f"webcam_start_time_{idx}" in st.session_state) or (transcript_key in st.session_state)
        audio_input_present = transcript_key in st.session_state  # gate for the block below
    else:
        st.markdown("#### 🎙️ Record Your Answer")
        st.caption("Click the mic below to start recording. Click again (or the stop button) to finish.")
        audio_input = st.audio_input("Record your answer", key=f"audio_input_{idx}")
        already_recorded = audio_input is not None
        audio_input_present = audio_input is not None

    # ── Timer (counts down until the candidate has started recording) ─────
    expired_auto_skip = _render_timer(idx, already_recorded=already_recorded)
    if expired_auto_skip:
        qa_pairs = st.session_state.get("qa_pairs", [])
        qa_pairs.append({
            "question": questions[idx],
            "answer": "(time expired — auto-skipped)",
        })
        st.session_state.qa_pairs = qa_pairs
        st.session_state.current_q_index = idx + 1
        st.session_state.pop(f"q_start_time_{idx}", None)
        st.rerun()
        return

    # ── Transcription (audio-only fallback path) + Confirm ────────────────
    if not use_webcam and audio_input_present:
        # Transcribe once per recording
        if transcript_key not in st.session_state:
            with st.spinner("🔄 Transcribing your answer..."):
                try:
                    audio_bytes_rec = audio_input.read()
                    text = transcribe_audio(audio_bytes_rec)
                    st.session_state[transcript_key] = text
                except TranscriptionError as e:
                    st.error(f"❌ Transcription failed: {e}")
                    st.stop()

    if transcript_key in st.session_state:
        # ── Delivery / confidence metrics (webcam path only) ───────────
        confidence_key = f"confidence_{idx}"
        confidence_data = st.session_state.get(confidence_key)
        if confidence_data:
            score = confidence_data["confidence_score"]
            color = "#16a34a" if score >= 7 else "#d97706" if score >= 4 else "#dc2626"
            eye = confidence_data.get("eye_contact_pct", -1)
            eye_str = f"{eye}%" if eye >= 0 else "N/A"
            notes_html = "".join(f"<li>{n}</li>" for n in confidence_data.get("notes", []))
            st.markdown(
                f"""
                <div style='border:1px solid #e2e8f0; border-radius:10px; padding:0.8rem 1rem;
                            margin-bottom:0.8rem; background:#f8fafc;'>
                    <p style='margin:0 0 0.3rem 0; font-weight:600; color:{color};'>
                        🎯 Delivery & Confidence: {score}/10
                    </p>
                    <p style='margin:0 0 0.3rem 0; color:#475569; font-size:0.85rem;'>
                        Pace: {confidence_data['wpm']} WPM · Filler words: {confidence_data['filler_count']}
                        · Eye contact: {eye_str}
                    </p>
                    <ul style='margin:0; padding-left:1.1rem; color:#64748b; font-size:0.82rem;'>
                        {notes_html}
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("#### ✏️ Your Answer (edit if needed)")
        edited_answer = st.text_area(
            "Transcribed answer",
            value=st.session_state[transcript_key],
            height=120,
            label_visibility="collapsed",
            key=f"edited_{idx}",
        )

        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button("✅ Confirm & Continue", use_container_width=True, type="primary", key=f"confirm_{idx}"):
                # Store this Q&A pair (with delivery metrics if we have them)
                qa_pairs = st.session_state.get("qa_pairs", [])
                qa_pairs.append({
                    "question": questions[idx],
                    "answer": edited_answer.strip(),
                    "confidence_metrics": confidence_data,
                })
                st.session_state.qa_pairs = qa_pairs
                st.session_state.current_q_index = idx + 1

                # Clean up transcript + confidence + timer state for this index
                st.session_state.pop(transcript_key, None)
                st.session_state.pop(confidence_key, None)
                st.session_state.pop(f"q_start_time_{idx}", None)

                st.rerun()

        with col2:
            if st.button("🔁 Re-record", use_container_width=True, key=f"rerecord_{idx}"):
                st.session_state.pop(transcript_key, None)
                st.session_state.pop(confidence_key, None)
                st.rerun()

    # ── Skip (for testing / accessibility) ────────────────
    with st.expander("⚙️ Options"):
        if st.button("⏭️ Skip this question", key=f"skip_{idx}"):
            qa_pairs = st.session_state.get("qa_pairs", [])
            qa_pairs.append({
                "question": questions[idx],
                "answer": "(skipped)",
            })
            st.session_state.qa_pairs = qa_pairs
            st.session_state.current_q_index = idx + 1
            st.session_state.pop(f"q_start_time_{idx}", None)
            st.session_state.pop(f"transcript_{idx}", None)
            st.session_state.pop(f"confidence_{idx}", None)
            st.rerun()
