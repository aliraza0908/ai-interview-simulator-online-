"""
pages_logic/summary_page.py — Results dashboard: scores, feedback, bar chart, PDF download.
"""

import streamlit as st
from database import save_interview
from utils.report_generator import PDFReport
from utils.personas import get_persona, get_interview_type, DEFAULT_PERSONA_KEY, DEFAULT_INTERVIEW_TYPE_KEY


def render():
    results = st.session_state.get("evaluation_results", [])
    user_name = st.session_state.get("user_name", "Candidate")
    persona = get_persona(st.session_state.get("persona_key", DEFAULT_PERSONA_KEY))
    itype = get_interview_type(st.session_state.get("interview_type_key", DEFAULT_INTERVIEW_TYPE_KEY))

    if not results:
        st.error("No results found. Please complete an interview first.")
        return

    scores = [r.get("score", 0) for r in results]
    avg = round(sum(scores) / len(scores), 2) if scores else 0
    confidence_scores = [r.get("confidence_score") for r in results if r.get("confidence_score") is not None]
    avg_confidence = round(sum(confidence_scores) / len(confidence_scores), 1) if confidence_scores else None

    # ── Save to DB (once) ──────────────────────────────────
    if not st.session_state.get("interview_saved"):
        try:
            save_interview(
                user_id=st.session_state.get("user_id"),
                cv_filename=st.session_state.get("cv_filename", "unknown.pdf"),
                responses_list=results,
                persona_key=st.session_state.get("persona_key", DEFAULT_PERSONA_KEY),
                interview_type_key=st.session_state.get("interview_type_key", DEFAULT_INTERVIEW_TYPE_KEY),
            )
            st.session_state.interview_saved = True
        except Exception as e:
            st.warning(f"⚠️ Could not save results to database: {e}")

    # ── Header ─────────────────────────────────────────────
    st.markdown(
        f"""
        <div style='text-align:center; padding:1.5rem 0 0.5rem 0;'>
            <span style='font-size:2.5rem;'>🏆</span>
            <h2 style='color:#1e40af; margin:0.3rem 0;'>Interview Complete!</h2>
            <p style='color:#64748b;'>Here's how you did, {user_name}.</p>
            <p style='color:#94a3b8; font-size:0.85rem; margin-top:0.2rem;'>
                {itype['icon']} {itype['label']} · {persona['avatar']} {persona['name']}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Overall score metric ───────────────────────────────
    col1, col2, col3 = st.columns(3)
    col1.metric("📊 Average Score", f"{avg}/10")
    col2.metric("✅ Questions Answered", len([r for r in results if r.get("answer_text") and r["answer_text"] != "(skipped)"]))
    col3.metric("📝 Total Questions", len(results))

    st.divider()

    # ── Bar chart ──────────────────────────────────────────
    st.markdown("### 📈 Score Breakdown")
    chart_data = {f"Q{r['question_number']}": r.get("score", 0) for r in results}

    try:
        import altair as alt
        import pandas as pd

        df = pd.DataFrame(
            {"Question": list(chart_data.keys()), "Score": list(chart_data.values())}
        )
        chart = (
            alt.Chart(df)
            .mark_bar(color="#3b82f6", cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X("Question:N", sort=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("Score:Q", scale=alt.Scale(domain=[0, 10])),
                tooltip=["Question", "Score"],
            )
            .properties(height=250)
        )
        st.altair_chart(chart, use_container_width=True)
    except ImportError:
        # Fallback: built-in bar chart
        import pandas as pd
        df = pd.DataFrame({"Score": chart_data})
        st.bar_chart(df)

    st.divider()

    # ── Per-question breakdown ─────────────────────────────
    st.markdown("### 🗂️ Detailed Feedback")
    for r in results:
        score = r.get("score", 0)
        color = "#16a34a" if score >= 7 else "#d97706" if score >= 4 else "#dc2626"
        label = "Excellent" if score >= 8 else "Good" if score >= 6 else "Fair" if score >= 4 else "Needs Work"

        with st.expander(f"Q{r['question_number']}  —  Score: {score}/10  ({label})", expanded=False):
            st.markdown(
                f"""
                <div style='border-left: 4px solid {color}; padding: 0.5rem 1rem; margin-bottom:0.5rem;
                            background:#f8fafc; border-radius:0 6px 6px 0;'>
                    <strong>Question:</strong><br>{r.get('question_text','')}
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown(f"**Your Answer:** {r.get('answer_text', '(no answer)')}")
            st.markdown(
                f"<span style='color:{color}; font-weight:600;'>Score: {score}/10</span>",
                unsafe_allow_html=True,
            )
            if r.get("feedback"):
                st.info(f"💬 **Feedback:** {r['feedback']}")
            missing_kw = r.get("missing_keywords", "")
            if isinstance(missing_kw, list):
                missing_kw = ", ".join(missing_kw)
            if missing_kw:
                st.warning(f"🔑 **Missing Keywords:** {missing_kw}")

    st.divider()

    # ── PDF Download ───────────────────────────────────────
    st.markdown("### 📥 Download Your Report")
    try:
        report = PDFReport(user_name=user_name, responses=results, average_score=avg)
        pdf_bytes = report.get_bytes()
        st.download_button(
            label="📥 Download PDF Report",
            data=pdf_bytes,
            file_name=f"interview_report_{user_name.replace(' ', '_')}.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary",
        )
    except Exception as e:
        st.error(f"❌ Could not generate PDF: {e}")

    st.divider()

    # ── Start New Interview ────────────────────────────────
    if st.button("🔄 Start New Interview", use_container_width=True):
        # Clear interview-related state but keep auth
        keys_to_clear = [
            "questions", "current_q_index", "qa_pairs", "evaluation_results",
            "cv_filename", "cv_text", "interview_saved",
            "persona_key", "interview_type_key", "timer_key",
        ]
        # Also clear tts, transcript, and timer caches
        prefixed_keys = [
            k for k in st.session_state.keys()
            if k.startswith(("tts_", "transcript_", "edited_", "q_start_time_"))
        ]
        for k in keys_to_clear + prefixed_keys:
            st.session_state.pop(k, None)

        st.session_state.app_stage = "upload"
        st.rerun()
