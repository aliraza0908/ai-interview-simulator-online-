"""
pages_logic/auth_page.py — Login & Sign-Up page.
Centered card layout with tabs, inline validation, friendly branding.
"""

import streamlit as st
from database import create_user, verify_user, DuplicateEmailError


def render():
    # ── Centered card via columns ──────────────────────────
    col_l, col_c, col_r = st.columns([1, 2.2, 1])
    with col_c:
        st.markdown(
            """
            <div style='text-align:center; padding: 2rem 0 0.5rem 0;'>
                <span style='font-size:3rem;'>🎙️</span>
                <h1 style='color:#1e40af; margin:0; font-size:2rem;'>AI Interview Simulator</h1>
                <p style='color:#64748b; margin-top:0.3rem;'>Practice. Improve. Get Hired.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.divider()

        tab_login, tab_signup = st.tabs(["🔑  Log In", "✨  Sign Up"])

        # ── LOG IN ─────────────────────────────────────────
        with tab_login:
            st.markdown("#### Welcome back!")
            email_in = st.text_input("Email", key="login_email", placeholder="you@example.com")
            pass_in = st.text_input("Password", type="password", key="login_pass", placeholder="Your password")

            if st.button("Log In →", use_container_width=True, type="primary", key="login_btn"):
                if not email_in.strip() or not pass_in:
                    st.error("Please enter your email and password.")
                else:
                    user = verify_user(email_in.strip(), pass_in)
                    if user:
                        st.session_state.user_id = user["id"]
                        st.session_state.user_name = user["name"]
                        st.session_state.user_email = user["email"]
                        st.session_state.app_stage = "upload"
                        st.success(f"Welcome back, {user['name']}! 🎉")
                        st.rerun()
                    else:
                        st.error("❌ Invalid email or password.")

        # ── SIGN UP ────────────────────────────────────────
        with tab_signup:
            st.markdown("#### Create your account")
            name_su = st.text_input("Full Name", key="su_name", placeholder="Jane Smith")
            email_su = st.text_input("Email", key="su_email", placeholder="you@example.com")
            pass_su = st.text_input("Password", type="password", key="su_pass", placeholder="Minimum 6 characters")
            pass_su2 = st.text_input("Confirm Password", type="password", key="su_pass2", placeholder="Repeat your password")

            if st.button("Create Account →", use_container_width=True, type="primary", key="signup_btn"):
                errors = []
                if not name_su.strip():
                    errors.append("Full name is required.")
                if not email_su.strip() or "@" not in email_su:
                    errors.append("A valid email address is required.")
                if len(pass_su) < 6:
                    errors.append("Password must be at least 6 characters.")
                if pass_su != pass_su2:
                    errors.append("Passwords don't match.")

                if errors:
                    for err in errors:
                        st.error(f"❌ {err}")
                else:
                    try:
                        user_id = create_user(name_su.strip(), email_su.strip(), pass_su)
                        st.session_state.user_id = user_id
                        st.session_state.user_name = name_su.strip()
                        st.session_state.user_email = email_su.strip().lower()
                        st.session_state.app_stage = "upload"
                        st.success("Account created! Welcome 🎉")
                        st.rerun()
                    except DuplicateEmailError:
                        st.error("❌ That email is already registered. Try logging in instead.")
                    except Exception as e:
                        st.error(f"❌ Something went wrong: {e}")

        st.markdown("<br>", unsafe_allow_html=True)
