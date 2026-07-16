import re
import os
import numpy as np

try:
    import cv2
    _cascade_path = None
    try:
        _p = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        if os.path.exists(_p):
            _cascade_path = _p
    except AttributeError:
        pass
    if not _cascade_path:
        _cv2_dir = os.path.dirname(cv2.__file__)
        _p = os.path.join(_cv2_dir, "data", "haarcascade_frontalface_default.xml")
        if os.path.exists(_p):
            _cascade_path = _p
    if _cascade_path:
        _FACE_CASCADE = cv2.CascadeClassifier(_cascade_path)
        CV2_AVAILABLE = True
    else:
        _FACE_CASCADE = None
        CV2_AVAILABLE = False
except Exception:
    cv2 = None
    _FACE_CASCADE = None
    CV2_AVAILABLE = False

FILLER_WORDS = [
    "um", "umm", "uh", "uhh", "er", "erm", "like", "you know", "i mean",
    "actually", "basically", "literally", "sort of", "kind of", "so yeah",
]

def detect_face_in_frame(frame_bgr) -> bool:
    if not CV2_AVAILABLE or _FACE_CASCADE is None or frame_bgr is None:
        return False
    try:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        faces = _FACE_CASCADE.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
        return len(faces) > 0
    except Exception:
        return False

def compute_eye_contact_pct(face_detected_flags: list) -> float:
    if not CV2_AVAILABLE or not face_detected_flags:
        return -1.0
    return round(100.0 * sum(1 for f in face_detected_flags if f) / len(face_detected_flags), 1)

def compute_speech_metrics(transcript: str, duration_seconds: float) -> dict:
    text = (transcript or "").strip()
    words = re.findall(r"[a-zA-Z']+", text)
    word_count = len(words)
    duration_minutes = max(duration_seconds, 1e-6) / 60.0
    wpm = round(word_count / duration_minutes, 1) if duration_minutes > 0 else 0.0
    lowered = text.lower()
    filler_count = 0
    for phrase in FILLER_WORDS:
        filler_count += len(re.findall(rf"\b{re.escape(phrase)}\b", lowered))
    filler_ratio = round(filler_count / word_count, 3) if word_count else 0.0
    return {"wpm": wpm, "word_count": word_count, "filler_count": filler_count, "filler_ratio": filler_ratio}

def derive_confidence_score(wpm: float, filler_ratio: float, eye_contact_pct: float) -> dict:
    score = 10.0
    notes = []
    if wpm <= 0:
        pass
    elif wpm < 90:
        score -= 2.0
        notes.append("Pace was a bit slow — try to keep your answer flowing.")
    elif wpm > 190:
        score -= 2.0
        notes.append("Pace was quite fast — slow down slightly for clarity.")
    else:
        notes.append("Good, natural speaking pace.")
    if filler_ratio > 0.08:
        score -= 2.5
        notes.append("Frequent filler words (um/like/uh) — try pausing silently instead.")
    elif filler_ratio > 0.04:
        score -= 1.0
        notes.append("Some filler words noticed — minor, but worth trimming.")
    else:
        notes.append("Minimal filler words — clean delivery.")
    if eye_contact_pct >= 0:
        if eye_contact_pct < 40:
            score -= 2.5
            notes.append("Low eye contact — try to look at the camera more.")
        elif eye_contact_pct < 70:
            score -= 1.0
            notes.append("Moderate eye contact — could be more consistent.")
        else:
            notes.append("Strong eye contact with the camera.")
    else:
        notes.append("Eye contact analysis not available in this environment.")
    score = max(0.0, min(10.0, round(score, 1)))
    return {"confidence_score": score, "notes": notes}

def summarize_for_prompt(metrics: dict) -> str:
    parts = [f"speaking pace ~{metrics.get('wpm', 0)} WPM", f"{metrics.get('filler_count', 0)} filler word(s)"]
    eye = metrics.get("eye_contact_pct", -1)
    if eye is not None and eye >= 0:
        parts.append(f"~{eye}% eye contact with the camera")
    else:
        parts.append("eye contact data unavailable")
    return ", ".join(parts)