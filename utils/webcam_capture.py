"""
utils/webcam_capture.py — Webcam-based answer recording.

Opens the candidate's webcam + mic via streamlit-webrtc when a question starts.
While they're speaking:
  - Live video preview is shown (so it *feels* like a real video interview).
  - Audio is incrementally drained from the WebRTC audio queue into an in-memory
    buffer (pydub AudioSegment).
  - Video frames are periodically sampled and run through face detection to build
    an eye-contact signal (utils/confidence_analyzer.py) — no raw video is stored,
    only a True/False "face visible" flag per sample, to keep memory small.

When the candidate clicks "Finished Speaking":
  - The buffered audio is exported to WAV bytes and sent through the existing
    AssemblyAI transcription pipeline (utils/stt_assembly.py) — same as before.
  - Speech-pace + filler-word metrics are computed from the transcript + elapsed
    time, combined with the eye-contact signal, into a confidence/delivery score.
  - Results are written into st.session_state so pages_logic/interview_page.py's
    existing edit/confirm UI can pick them up unchanged.

If streamlit-webrtc (or the browser/camera) isn't available, this module reports
that gracefully so the caller can fall back to the original audio-only recorder.
"""

import io
import time
import queue
import streamlit as st

from utils.stt_assembly import transcribe_audio, TranscriptionError
from utils.confidence_analyzer import (
    detect_face_in_frame,
    compute_eye_contact_pct,
    compute_speech_metrics,
    derive_confidence_score,
)

try:
    from streamlit_webrtc import webrtc_streamer, WebRtcMode
    import pydub
    _HAS_WEBRTC = True
except ImportError:
    _HAS_WEBRTC = False

try:
    from streamlit_autorefresh import st_autorefresh
    _HAS_AUTOREFRESH = True
except ImportError:
    _HAS_AUTOREFRESH = False


VIDEO_SAMPLE_EVERY_N_DRAINS = 1  # sample ~1 frame per drain tick (every ~1.2s)


def webcam_available() -> bool:
    return _HAS_WEBRTC


def _drain_audio(webrtc_ctx, idx: int):
    """Pull whatever audio frames are currently queued and append to the running buffer."""
    if webrtc_ctx.audio_receiver is None:
        return
    buf_key = f"webcam_audio_buf_{idx}"
    if buf_key not in st.session_state:
        st.session_state[buf_key] = pydub.AudioSegment.empty()

    try:
        frames = webrtc_ctx.audio_receiver.get_frames(timeout=0.5)
    except queue.Empty:
        return

    for frame in frames:
        try:
            sound = pydub.AudioSegment(
                data=frame.to_ndarray().tobytes(),
                sample_width=frame.format.bytes,
                frame_rate=frame.sample_rate,
                channels=len(frame.layout.channels),
            )
            st.session_state[buf_key] += sound
        except Exception:
            continue  # skip a malformed frame rather than crash the interview


def _drain_video_sample(webrtc_ctx, idx: int):
    """Pull one (or a few) video frames, run face detection, and record the flag."""
    if webrtc_ctx.video_receiver is None:
        return
    flags_key = f"webcam_face_flags_{idx}"
    if flags_key not in st.session_state:
        st.session_state[flags_key] = []

    try:
        frames = webrtc_ctx.video_receiver.get_frames(timeout=0.5)
    except queue.Empty:
        return

    for frame in frames[-1:]:  # only need one sample per tick, cheapest = the latest
        try:
            img = frame.to_ndarray(format="bgr24")
            st.session_state[flags_key].append(detect_face_in_frame(img))
        except Exception:
            continue


def _finalize(idx: int) -> bool:
    """
    Export the buffered audio, transcribe it, compute confidence metrics, and
    store everything into the session_state keys interview_page.py expects.
    Returns True on success, False on failure (caller shows an error + lets them retry).
    """
    buf_key = f"webcam_audio_buf_{idx}"
    audio_segment = st.session_state.get(buf_key)

    if audio_segment is None or len(audio_segment) < 300:  # <0.3s — essentially nothing recorded
        st.error("❌ No audio was captured. Please make sure your mic is enabled and try again.")
        return False

    wav_buf = io.BytesIO()
    audio_segment.export(wav_buf, format="wav")
    wav_bytes = wav_buf.getvalue()

    try:
        text = transcribe_audio(wav_bytes)
    except TranscriptionError as e:
        st.error(f"❌ Transcription failed: {e}")
        return False

    duration_seconds = len(audio_segment) / 1000.0
    speech_metrics = compute_speech_metrics(text, duration_seconds)

    flags_key = f"webcam_face_flags_{idx}"
    eye_contact_pct = compute_eye_contact_pct(st.session_state.get(flags_key, []))

    confidence = derive_confidence_score(
        wpm=speech_metrics["wpm"],
        filler_ratio=speech_metrics["filler_ratio"],
        eye_contact_pct=eye_contact_pct,
    )

    st.session_state[f"transcript_{idx}"] = text
    st.session_state[f"confidence_{idx}"] = {
        **speech_metrics,
        "eye_contact_pct": eye_contact_pct,
        "confidence_score": confidence["confidence_score"],
        "notes": confidence["notes"],
    }

    # Clean up recording buffers — no longer needed once finalized.
    st.session_state.pop(buf_key, None)
    st.session_state.pop(flags_key, None)
    st.session_state.pop(f"webcam_start_time_{idx}", None)
    return True


def render_webcam_recorder(idx: int):
    """
    Render the webcam preview + recording controls for question `idx`.
    Call this once per question render(); it manages its own incremental state.
    Once finished, it populates st.session_state[f"transcript_{idx}"] and
    st.session_state[f"confidence_{idx}"] — the caller (interview_page.py) should
    check for `transcript_{idx}` afterward exactly as it did with the old recorder.
    """
    if not _HAS_WEBRTC:
        st.info("🎥 Webcam recording isn't available (streamlit-webrtc not installed).")
        return

    transcript_key = f"transcript_{idx}"
    if transcript_key in st.session_state:
        # Already finalized for this question — nothing left to render here.
        return

    st.markdown("#### 🎥 Webcam Interview")
    st.caption("Your camera and mic are live. Speak your answer, then click **Finished Speaking** below.")

    webrtc_ctx = webrtc_streamer(
        key=f"webcam_{idx}",
        mode=WebRtcMode.SENDONLY,
        media_stream_constraints={"video": {"width": 320, "height": 240}, "audio": True},
        audio_receiver_size=2048,
        video_receiver_size=128,
        async_processing=True,
    )

    if webrtc_ctx.state.playing:
        start_key = f"webcam_start_time_{idx}"
        if start_key not in st.session_state:
            st.session_state[start_key] = time.time()

        _drain_audio(webrtc_ctx, idx)
        _drain_video_sample(webrtc_ctx, idx)

        n_flags = len(st.session_state.get(f"webcam_face_flags_{idx}", []))
        st.caption(f"🔴 Recording... ({n_flags} webcam samples captured so far)")

        if _HAS_AUTOREFRESH:
            st_autorefresh(interval=1200, key=f"webcam_refresh_{idx}", limit=600)

    has_buffered_audio = len(st.session_state.get(f"webcam_audio_buf_{idx}", pydub.AudioSegment.empty())) > 0
    finish_disabled = not (webrtc_ctx.state.playing or has_buffered_audio)

    if st.button("🛑 Finished Speaking", type="primary", use_container_width=True,
                 key=f"finish_webcam_{idx}", disabled=finish_disabled):
        # One last drain in case frames arrived between the last refresh and the click.
        if webrtc_ctx.audio_receiver is not None:
            _drain_audio(webrtc_ctx, idx)
        if webrtc_ctx.video_receiver is not None:
            _drain_video_sample(webrtc_ctx, idx)

        with st.spinner("🔄 Transcribing your answer..."):
            success = _finalize(idx)
        if success:
            st.rerun()
