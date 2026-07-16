"""
app.py — AI Interview Simulator — Main Streamlit Entrypoint.

Stage machine via st.session_state.app_stage:
  "auth"       → Login / Sign-Up
  "upload"     → CV upload + question generation
  "interview"  → Voice Q&A loop
  "evaluating" → Evaluation loading screen
  "summary"    → Results + PDF download
"""

import streamlit as st
from database import init_db
from database import get_user_interview_history
from utils.personas import get_persona, get_interview_type

# ── Page config — must be first Streamlit call ─────────────
st.set_page_config(
    page_title="AI Interview Simulator",
    page_icon="🎙️",
    layout="centered",
    initial_sidebar_state="auto",
)

# ── Initialize DB on every cold start ──────────────────────
init_db()

# ── Session state defaults ─────────────────────────────────
if "app_stage" not in st.session_state:
    st.session_state.app_stage = "auth"

# ── Global CSS ─────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* Hide default Streamlit header/footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Card-style containers */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px;
        padding: 0.5rem;
    }

    /* Primary button override */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #1e40af, #3b82f6);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        letter-spacing: 0.02em;
        transition: all 0.2s;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #1e3a8a, #2563eb);
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(59,130,246,0.35);
    }

    /* Tab style */
    .stTabs [data-baseweb="tab"] {
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Sidebar (only when logged in) ─────────────────────────
def _render_sidebar():
    if st.session_state.get("user_id") and st.session_state.app_stage != "auth":
        with st.sidebar:
            st.markdown(
                f"""
                <div style='text-align:center; padding:1rem 0;'>
                    <span style='font-size:2rem;'>👤</span>
                    <h3 style='margin:0.3rem 0 0 0; color:#1e40af;'>
                        {st.session_state.get('user_name', '')}
                    </h3>
                    <p style='color:#64748b; font-size:0.8rem; margin:0;'>
                        {st.session_state.get('user_email', '')}
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.divider()

            # Stage indicator
            stage_labels = {
                "upload": "📄 Upload CV",
                "interview": "🎙️ In Interview",
                "evaluating": "⏳ Evaluating",
                "summary": "📊 Results",
            }
            current = st.session_state.app_stage
            if current in stage_labels:
                st.markdown(f"**Current Stage:** {stage_labels[current]}")
                st.divider()

            # Past interview history
            try:
                history = get_user_interview_history(st.session_state.user_id)
                if history:
                    st.markdown("#### 📋 Past Interviews")
                    for h in history[:5]:  # show latest 5
                        avg = h.get("average_score")
                        avg_str = f"{avg:.1f}/10" if avg is not None else "N/A"
                        date_str = str(h.get("created_at", ""))[:10]
                        p = get_persona(h.get("persona_key") or "")
                        it = get_interview_type(h.get("interview_type_key") or "")
                        st.markdown(
                            f"""
                            <div style='background:#f0f9ff; border-radius:6px;
                                        padding:0.4rem 0.6rem; margin-bottom:0.4rem;
                                        border-left:3px solid #3b82f6;'>
                                <small style='color:#1e40af; font-weight:600;'>{date_str}</small><br>
                                <small style='color:#475569;'>Avg: {avg_str} · {h.get('cv_filename','')}</small><br>
                                <small style='color:#94a3b8;'>{it['icon']} {it['label']} · {p['avatar']} {p['name']}</small>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
            except Exception:
                pass  # history is optional, don't crash

            st.divider()
            if st.button("🚪 Log Out", use_container_width=True):
                # Clear all session state
                st.session_state.clear()
                st.session_state.app_stage = "auth"
                st.rerun()


# ── Page routing ───────────────────────────────────────────
_render_sidebar()

stage = st.session_state.app_stage

if stage == "auth":
    from pages_logic.auth_page import render
    render()

elif stage == "upload":
    # Guard: must be logged in
    if not st.session_state.get("user_id"):
        st.session_state.app_stage = "auth"
        st.rerun()
    from pages_logic.upload_page import render
    render()

elif stage == "interview":
    if not st.session_state.get("user_id"):
        st.session_state.app_stage = "auth"
        st.rerun()
    from pages_logic.interview_page import render
    render()

elif stage == "evaluating":
    if not st.session_state.get("user_id"):
        st.session_state.app_stage = "auth"
        st.rerun()

    # ── Evaluation loading stage ───────────────────────────
    st.markdown(
        """
        <div style='text-align:center; padding:3rem 0;'>
            <span style='font-size:3rem;'>🤖</span>
            <h2 style='color:#1e40af;'>Evaluating Your Interview...</h2>
            <p style='color:#64748b;'>Gemini AI is analyzing your answers. Please wait.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    qa_pairs = st.session_state.get("qa_pairs", [])
    if not qa_pairs:
        st.error("No answers found. Please complete the interview.")
        if st.button("Start Over"):
            st.session_state.app_stage = "upload"
            st.rerun()
    else:
        from utils.evaluator_gemini import evaluate_all_answers
        with st.spinner("Analyzing all answers with Gemini..."):
            results = evaluate_all_answers(
                qa_pairs,
                persona_key=st.session_state.get("persona_key", "friendly_tech"),
                interview_type_key=st.session_state.get("interview_type_key", "mixed"),
            )

        st.session_state.evaluation_results = results
        st.session_state.interview_saved = False  # will be saved in summary page
        st.session_state.app_stage = "summary"
        st.rerun()

elif stage == "summary":
    if not st.session_state.get("user_id"):
        st.session_state.app_stage = "auth"
        st.rerun()
    from pages_logic.summary_page import render
    render()

else:
    # Unknown stage fallback
    st.session_state.app_stage = "auth"
    st.rerun()
