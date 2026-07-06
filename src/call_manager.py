"""
call_manager.py

Owns the Twilio call lifecycle:
  1. Places the outbound call to the practice's test line.
  2. Spins up a small FastAPI/websocket server that Twilio connects to for
     the live Media Stream (this is how audio gets to/from voice_bridge.py).
  3. Starts Twilio's own dual-channel call recording.
  4. Assembles the live transcript as it streams in, and writes it + metadata
     to disk when the call ends.

Run via main.py, not directly.
"""

import asyncio
import json
import os
import time
import uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket
from twilio.rest import Client as TwilioClient
from twilio.twiml.voice_response import VoiceResponse, Connect

from scenarios import Scenario
from voice_bridge import RealtimeVoiceBridge

REPO_ROOT = Path(__file__).resolve().parent.parent
TRANSCRIPTS_DIR = REPO_ROOT / "transcripts"
RECORDINGS_DIR = REPO_ROOT / "recordings"

app = FastAPI()

# Simple in-process registry so the websocket handler knows which scenario
# is active for the call that's about to connect. Fine for our use case:
# one outbound call at a time, run sequentially.
_active_call: dict = {}


def _twiml_for_stream(public_ws_url: str) -> str:
    """Builds the TwiML that tells Twilio to open a Media Stream to us."""
    response = VoiceResponse()
    connect = Connect()
    connect.stream(url=public_ws_url)
    response.append(connect)
    return str(response)


@app.websocket("/media-stream")
async def media_stream_endpoint(websocket: WebSocket):
    await websocket.accept()

    scenario: Scenario = _active_call["scenario"]
    call_record = _active_call["record"]

    def on_transcript_chunk(role: str, text: str):
        if not text:
            return
        call_record["transcript_events"].append({
            "role": role,
            "text": text,
            "t": round(time.time() - call_record["start_time"], 2),
        })

    bridge = RealtimeVoiceBridge(
        twilio_ws=websocket,
        system_prompt=scenario.system_prompt(),
        on_transcript_chunk=on_transcript_chunk,
    )

    try:
        await bridge.run()
    finally:
        call_record["ended"] = True


class CallSession:
    """
    Orchestrates a single outbound test call: places it, waits for it to
    complete, then persists transcript + metadata. The audio recording itself
    is fetched separately via Twilio's Recording API (see fetch_recording).
    """

    def __init__(self, scenario: Scenario, twilio_number: str, target_number: str,
                 public_base_url: str):
        self.scenario = scenario
        self.twilio_number = twilio_number
        self.target_number = target_number
        self.public_base_url = public_base_url.rstrip("/")
        self.client = TwilioClient(
            os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"]
        )
        self.call_id = f"{scenario.id}_{uuid.uuid4().hex[:8]}"

    async def run(self) -> dict:
        record = {
            "call_id": self.call_id,
            "scenario_id": self.scenario.id,
            "scenario_name": self.scenario.name,
            "target_bug": self.scenario.target_bug,
            "success_signal": self.scenario.success_signal,
            "start_time": time.time(),
            "transcript_events": [],
            "ended": False,
        }
        _active_call.clear()
        _active_call.update({"scenario": self.scenario, "record": record})

        ws_url = f"{self.public_base_url.replace('https://', 'wss://')}/media-stream"
        twiml = _twiml_for_stream(ws_url)

        call = self.client.calls.create(
            to=self.target_number,
            from_=self.twilio_number,
            twiml=twiml,
            record=True,
            recording_channels="dual",
            timeout=self.scenario.max_duration_sec,
        )
        record["twilio_call_sid"] = call.sid

        # Poll until Twilio reports the call finished (simplest approach for
        # a sequential test harness; a webhook-based status callback would be
        # the production-grade version, which the brief says isn't required).
        while True:
            await asyncio.sleep(3)
            status = self.client.calls(call.sid).fetch().status
            if status in ("completed", "busy", "failed", "no-answer", "canceled"):
                break
            if time.time() - record["start_time"] > self.scenario.max_duration_sec + 30:
                break

        record["end_time"] = time.time()
        record["duration_sec"] = round(record["end_time"] - record["start_time"], 1)
        record["final_status"] = status

        self._persist_transcript(record)
        recording_path = self._fetch_recording(call.sid)
        record["recording_path"] = str(recording_path) if recording_path else None
        self._persist_metadata(record)
        return record

    def _persist_transcript(self, record: dict):
        path = TRANSCRIPTS_DIR / f"{record['call_id']}.txt"
        lines = [f"# Scenario: {record['scenario_name']} ({record['scenario_id']})",
                 f"# Target bug probed: {record['target_bug']}", ""]
        for event in record["transcript_events"]:
            speaker = "PATIENT (bot)" if event["role"] == "patient_bot" else "PRACTICE AGENT"
            lines.append(f"[{event['t']:>6.2f}s] {speaker}: {event['text']}")
        path.write_text("\n".join(lines), encoding="utf-8")
        record["transcript_path"] = str(path)

    def _fetch_recording(self, call_sid: str):
        import time
        import requests

        recordings = None
        for attempt in range(3):
            recs = self.client.recordings.list(call_sid=call_sid, limit=1)
            if recs:
                recordings = recs
                break
            print(f"[info] recording not ready yet for {call_sid}, retrying in 10s... ({attempt+1}/3)")
            time.sleep(10)

        if not recordings:
            print(f"[warn] no recording found yet for {call_sid}; "
                  f"Twilio may still be processing it — check back and re-download.")
            return None
            
        recording = recordings[0]
        # Twilio serves .mp3 directly via the media URL + extension.
        media_url = f"https://api.twilio.com{recording.uri.replace('.json', '.mp3')}"
        out_path = RECORDINGS_DIR / f"{call_sid}.mp3"

        import requests
        
        for attempt in range(3):
            resp = requests.get(
                media_url,
                auth=(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"]),
            )
            if resp.status_code == 200:
                out_path.write_bytes(resp.content)
                return out_path
            print(f"[info] recording media not ready (HTTP {resp.status_code}), retrying...")
            time.sleep(10)
            
        print(f"[warn] failed to download recording for {call_sid} after 3 attempts.")
        return None

    def _persist_metadata(self, record: dict):
        path = TRANSCRIPTS_DIR / f"{record['call_id']}.json"
        # transcript_events can be large/verbose; keep json metadata compact
        meta = {k: v for k, v in record.items() if k != "transcript_events"}
        path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def start_media_server(port: int = 8765):
    """Run this in a background thread/process before placing calls."""
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
