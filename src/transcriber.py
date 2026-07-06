"""
transcriber.py

The primary transcript for each call is built LIVE during the call from the
Realtime API's own transcription events (see call_manager.py /
voice_bridge.py) — that's more reliable for speaker attribution since we
already know which stream is which.

This module is a SUPPLEMENTARY/fallback path: if you want a second-pass,
audio-file-based diarized transcript (e.g. to double check the live one, or
because the live transcript came out empty/corrupted for a call), run this
against the saved recording using Whisper.

Not required for the pipeline to work end-to-end, but useful for QA.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types

REPO_ROOT = Path(__file__).resolve().parent.parent
RECORDINGS_DIR = REPO_ROOT / "recordings"
TRANSCRIPTS_DIR = REPO_ROOT / "transcripts"


def transcribe_recording(recording_path: Path) -> str:
    """
    Runs Gemini over a saved dual-channel recording to generate a transcript.
    This serves as a fallback or sanity check against the live transcripts.
    """
    client = genai.Client() # Uses GEMINI_API_KEY
    
    print(f"Uploading {recording_path.name} to Gemini for transcription...")
    audio_file = client.files.upload(file=str(recording_path), config={'display_name': recording_path.name})
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                audio_file, 
                "Please transcribe this conversation exactly as spoken. Add speaker labels like 'Caller:' or 'Agent:' if possible."
            ],
            config=types.GenerateContentConfig(temperature=0.0)
        )
        return response.text
    finally:
        # Always clean up the file
        client.files.delete(name=audio_file.name)


def verify_all_recordings():
    """Utility: re-transcribes every saved recording as a sanity check
    against the live transcripts already in transcripts/."""
    for recording_path in sorted(RECORDINGS_DIR.glob("*.mp3")):
        text = transcribe_recording(recording_path)
        out_path = TRANSCRIPTS_DIR / f"{recording_path.stem}_gemini_check.txt"
        out_path.write_text(text, encoding="utf-8")
        print(f"Wrote {out_path}")


if __name__ == "__main__":
    verify_all_recordings()
