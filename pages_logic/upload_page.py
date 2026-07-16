"""
pages_logic/upload_page.py — Profile/Welcome page + CV upload + interview setup + question generation.
"""

import streamlit as st
from utils.cv_parser import extract_cv_text
from utils.question_generator import generate_questions_from_cv
from utils.personas import (
    PERSONAS,
    INTERVIEW_TYPES,
    TIMER_MODES,
    DEFAULT_PERSONA_KEY,
    DEFAULT_INTERVIEW_TYPE_KEY,
    DEFAULT_TIMER_KEY,
)


def render():
    st.markdown(
        f"""
        <div style='text-align:center; padding:1.5rem 0 0.5rem 0;'>
            <h2 style='color:#1e40af;'>Welcome, {st.session_state.get('user_name', 'Candidate')}! 👋</h2>
            <p style='color:#64748b;'>Set up your mock interview, then upload your CV.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_l, col_c, col_r = st.columns([1, 3, 1])
    with col_c:
        # ── User info card ─────────────────────────────────
        with st.container(border=True):
            st.markdown("#### 👤 Your Profile")
            c1, c2 = st.columns(2)
            c1.metric("Name", st.session_state.get("user_name", "—"))
            c2.metric("Email", st.session_state.get("user_email", "—"))

        st.markdown("---")

        # ── Interview Setup: persona, type, timer ───────────
        st.markdown("#### 🎭 Choose Your Interviewer")
        persona_keys = list(PERSONAS.keys())
        persona_key = st.radio(
            "Interviewer persona",
            options=persona_keys,
            format_func=lambda k: f"{PERSONAS[k]['avatar']} {PERSONAS[k]['name']} — {PERSONAS[k]['title']}",
            index=persona_keys.index(DEFAULT_PERSONA_KEY),
            label_visibility="collapsed",
        )
        st.caption(PERSONAS[persona_key]["tagline"])

        st.markdown("#### 🗂️ Choose Interview Type")
        itype_keys = list(INTERVIEW_TYPES.keys())
        itype_key = st.selectbox(
            "Interview type",
            options=itype_keys,
            format_func=lambda k: f"{INTERVIEW_TYPES[k]['icon']} {INTERVIEW_TYPES[k]['label']}",
            index=itype_keys.index(DEFAULT_INTERVIEW_TYPE_KEY),
            label_visibility="collapsed",
        )
        st.caption(INTERVIEW_TYPES[itype_key]["description"])

        st.markdown("#### ⏱️ Time Pressure")
        timer_keys = list(TIMER_MODES.keys())
        timer_key = st.select_slider(
            "Time pressure",
            options=timer_keys,
            value=DEFAULT_TIMER_KEY,
            format_func=lambda k: TIMER_MODES[k]["label"],
            label_visibility="collapsed",
        )
        if TIMER_MODES[timer_key]["auto_skip"]:
            st.caption("⚠️ Strict mode auto-skips a question when time runs out.")

        st.markdown("---")

        # ── CV Upload ──────────────────────────────────────
        st.markdown("#### 📄 Upload Your CV")
        st.caption("Supported formats: PDF or DOCX")

        uploaded_file = st.file_uploader(
            "Drop your CV here",
            type=["pdf", "docx"],
            label_visibility="collapsed",
        )

        num_questions = st.slider(
            "Number of interview questions", min_value=5, max_value=12, value=8, step=1
        )

        start_disabled = uploaded_file is None

        if uploaded_file:
            st.success(f"✅ File ready: **{uploaded_file.name}**")

        if st.button(
            "🎙️ Start Interview",
            use_container_width=True,
            type="primary",
            disabled=start_disabled,
        ):
            with st.spinner("📖 Reading your CV..."):
                try:
                    cv_text = extract_cv_text(uploaded_file)
                except Exception:
                    st.stop()

            with st.spinner("🤖 Generating personalized questions from your CV..."):
                try:
                    questions = generate_questions_from_cv(
                        cv_text,
                        num_questions=num_questions,
                        persona_key=persona_key,
                        interview_type_key=itype_key,
                    )
                except Exception:
                    st.stop()

            # Store in session
            st.session_state.cv_filename = uploaded_file.name
            st.session_state.cv_text = cv_text
            st.session_state.questions = questions
            st.session_state.current_q_index = 0
            st.session_state.qa_pairs = []  # will accumulate {question, answer}
            st.session_state.persona_key = persona_key
            st.session_state.interview_type_key = itype_key
            st.session_state.timer_key = timer_key
            st.session_state.app_stage = "interview"
            st.success(f"✅ Generated {len(questions)} questions! Starting interview...")
            st.rerun()
