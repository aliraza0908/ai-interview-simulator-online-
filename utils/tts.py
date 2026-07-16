"""
utils/tts.py — Text-to-Speech using gTTS. Returns in-memory audio bytes.

Supports a `tld` parameter so different interviewer personas can sound subtly
different (gTTS has no separate "voices", but the Google Translate TLD changes
the accent enough to feel like a different speaker — see utils/personas.py).
"""

import io
import streamlit as st


def text_to_speech(text: str, tld: str = "com") -> bytes | None:
    """
    Convert text to speech using gTTS.
    tld: Google Translate top-level domain controlling accent
         ("com"=US, "co.uk"=British, "com.au"=Australian, "co.in"=Indian English).
    Returns audio bytes (MP3) or None if TTS fails.
    Requires internet connection.
    """
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang="en", slow=False, tld=tld)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        # Don't crash — caller will show text fallback
        st.warning(f"⚠️ Text-to-speech unavailable (requires internet): {e}. Showing question as text only.")
        return None
