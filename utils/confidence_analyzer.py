"""
utils/confidence_analyzer.py — Lightweight, heuristic "delivery & confidence" analysis.

Deliberately simple (no heavy ML / emotion models) so it installs fast and runs in
real time during an interview:
  - Eye contact proxy: % of sampled webcam frames where a face was detected via
    OpenCV's Haar cascade (a face pointed roughly at the camera = "looking at it").
  - Speaking pace: words-per-minute from the transcript + recording duration.
  - Filler words: ratio of filler words ("um", "uh", "like", "you know", ...) to
    total words.

These three signals are combined into a single 0-10 confidence_score with short,
human-readable notes. This is a heuristic, not a clinical assessment — it's meant
to nudge the candidate's awareness, not to be a hard judgment.
"""

import re
import cv2
import numpy as np

_FACE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

# Common English filler words/phrases (lowercase, word-boundary matched)
FILLER_WORDS = [
    "um", "umm", "uh", "uhh", "er", "erm", "like", "you know", "i mean",
    "actually", "basically", "literally", "sort of", "kind of", "so yeah",
]


def detect_face_in_frame(frame_bgr: "np.ndarray") -> bool:
    """
    Return True if at least one face is detected in this BGR frame (webcam snapshot).
    Used as a simple proxy for 'looking at the camera'.
    """
    try:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        faces = _FACE_CASCADE.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
        )
        return len(faces) > 0
    except Exception:
        # Never let a CV hiccup break the interview flow.
        return False


def compute_eye_contact_pct(face_detected_flags: list) -> float:
    """
    face_detected_flags: list of booleans sampled periodically during the answer.
    Returns percentage (0-100) of samples where a face was visible/facing the camera.
    Returns -1 if no samples were collected (so callers can distinguish "no data").
    """
    if not face_detected_flags:
        return -1.0
    return round(100.0 * sum(1 for f in face_detected_flags if f) / len(face_detected_flags), 1)


def compute_speech_metrics(transcript: str, duration_seconds: float) -> dict:
    """
    Compute words-per-minute and filler-word ratio from the final transcript text
    and the approximate recording duration.
    Returns {"wpm": float, "word_count": int, "filler_count": int, "filler_ratio": float}
    """
    text = (transcript or "").strip()
    words = re.findall(r"[a-zA-Z']+", text)
    word_count = len(words)

    duration_minutes = max(duration_seconds, 1e-6) / 60.0
    wpm = round(word_count / duration_minutes, 1) if duration_minutes > 0 else 0.0

    lowered = text.lower()
    filler_count = 0
    for phrase in FILLER_WORDS:
        # \b word-boundary match so "like" doesn't match inside "likely"
        filler_count += len(re.findall(rf"\b{re.escape(phrase)}\b", lowered))

    filler_ratio = round(filler_count / word_count, 3) if word_count else 0.0

    return {
        "wpm": wpm,
        "word_count": word_count,
        "filler_count": filler_count,
        "filler_ratio": filler_ratio,
    }


def derive_confidence_score(wpm: float, filler_ratio: float, eye_contact_pct: float) -> dict:
    """
    Combine the three heuristic signals into a single 0-10 confidence score plus
    short human-readable notes. Ideal spoken-English pace is roughly 110-170 WPM.
    """
    score = 10.0
    notes = []

    # ── Pacing ──────────────────────────────────────────
    if wpm <= 0:
        pass  # no speech detected at all — leave pacing untouched, other checks will catch it
    elif wpm < 90:
        score -= 2.0
        notes.append("Pace was a bit slow — try to keep your answer flowing.")
    elif wpm > 190:
        score -= 2.0
        notes.append("Pace was quite fast — slow down slightly for clarity.")
    else:
        notes.append("Good, natural speaking pace.")

    # ── Filler words ────────────────────────────────────
    if filler_ratio > 0.08:
        score -= 2.5
        notes.append("Frequent filler words (um/like/uh) — try pausing silently instead.")
    elif filler_ratio > 0.04:
        score -= 1.0
        notes.append("Some filler words noticed — minor, but worth trimming.")
    else:
        notes.append("Minimal filler words — clean delivery.")

    # ── Eye contact (only scored if we actually have webcam samples) ─────
    if eye_contact_pct >= 0:
        if eye_contact_pct < 40:
            score -= 2.5
            notes.append("Low eye contact with the camera — try to look at it more while answering.")
        elif eye_contact_pct < 70:
            score -= 1.0
            notes.append("Moderate eye contact — could be more consistent.")
        else:
            notes.append("Strong eye contact with the camera.")

    score = max(0.0, min(10.0, round(score, 1)))
    return {"confidence_score": score, "notes": notes}


def summarize_for_prompt(metrics: dict) -> str:
    """
    Build a short plain-English summary of delivery metrics to optionally pass
    into the LLM evaluation prompt, so written feedback can reference delivery too.
    """
    parts = [f"speaking pace ~{metrics.get('wpm', 0)} WPM", f"{metrics.get('filler_count', 0)} filler word(s)"]
    eye = metrics.get("eye_contact_pct", -1)
    if eye is not None and eye >= 0:
        parts.append(f"~{eye}% eye contact with the camera")
    return ", ".join(parts)
