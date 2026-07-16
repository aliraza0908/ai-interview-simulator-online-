"""
utils/stt_assembly.py — Speech-to-Text via AssemblyAI API.
Takes audio bytes from st.audio_input() and returns transcribed text.
"""

import io
import time
import requests
import streamlit as st
from config import ASSEMBLY_API_KEY

UPLOAD_URL = "https://api.assemblyai.com/v2/upload"
TRANSCRIPT_URL = "https://api.assemblyai.com/v2/transcript"
HEADERS = {"authorization": ASSEMBLY_API_KEY}


class TranscriptionError(Exception):
    """Raised when AssemblyAI transcription fails."""
    pass


def _upload_audio(audio_bytes: bytes) -> str:
    """Upload audio bytes to AssemblyAI and return the upload URL."""
    response = requests.post(
        UPLOAD_URL,
        headers=HEADERS,
        data=audio_bytes,
        timeout=60,
    )
    if response.status_code != 200:
        raise TranscriptionError(f"Audio upload failed: {response.status_code} — {response.text}")
    return response.json()["upload_url"]


def _request_transcript(audio_url: str) -> str:
    """Submit transcription job and return the transcript id."""
    payload = {"audio_url": audio_url, "language_code": "en"}
    response = requests.post(TRANSCRIPT_URL, json=payload, headers=HEADERS, timeout=30)
    if response.status_code != 200:
        raise TranscriptionError(f"Transcript request failed: {response.status_code} — {response.text}")
    return response.json()["id"]


def _poll_transcript(transcript_id: str, max_wait: int = 120) -> str:
    """Poll until transcript is completed. Returns transcribed text."""
    poll_url = f"{TRANSCRIPT_URL}/{transcript_id}"
    elapsed = 0
    while elapsed < max_wait:
        response = requests.get(poll_url, headers=HEADERS, timeout=30)
        data = response.json()
        status = data.get("status")
        if status == "completed":
            return data.get("text", "")
        elif status == "error":
            raise TranscriptionError(f"Transcription error: {data.get('error', 'Unknown error')}")
        time.sleep(3)
        elapsed += 3
    raise TranscriptionError("Transcription timed out after 2 minutes.")


def transcribe_audio(audio_bytes: bytes) -> str:
    """
    Full pipeline: upload → request → poll → return text.
    Raises TranscriptionError on any failure.
    audio_bytes: raw bytes from st.audio_input().read() or similar.
    """
    if not audio_bytes:
        raise TranscriptionError("No audio data received.")
    if not ASSEMBLY_API_KEY or ASSEMBLY_API_KEY == "your_assemblyai_api_key_here":
        raise TranscriptionError("AssemblyAI API key not configured in config.py.")

    audio_url = _upload_audio(audio_bytes)
    transcript_id = _request_transcript(audio_url)
    text = _poll_transcript(transcript_id)

    if not text or not text.strip():
        raise TranscriptionError("Transcription returned empty text. Please try recording again.")
    return text.strip()
