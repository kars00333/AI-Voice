"""
voice_bridge.py

Bridges a live Twilio Media Stream (the phone call audio) to the OpenAI
Realtime API (speech-to-speech). This is the "bot brain" — it receives the
agent's audio from the call, streams it to the Realtime model, and streams
the model's spoken response back into the call.

Why Realtime API instead of STT -> LLM -> TTS:
  A chained pipeline (transcribe -> think -> synthesize) adds the latency of
  three separate network round trips per turn, which tends to produce the
  awkward multi-second pauses that the challenge explicitly flags as a
  rejection risk. The Realtime API keeps audio-in -> audio-out in a single
  streaming session, which is the only reliable way to hit natural
  conversational pacing on a first build.

This module is intentionally a single-purpose bridge: it does not know
about scenarios, scoring, or file I/O beyond raw audio bytes. Higher-level
orchestration (which scenario to run, when to hang up) lives in call_manager.py.
"""

import asyncio
import base64
import json
import os
import audioop
from typing import Optional, Callable

from google import genai
from google.genai import types

class RealtimeVoiceBridge:
    """
    Manages one bridged session between a Twilio Media Stream websocket and
    the Gemini Multimodal Live API websocket, for the duration of a single call.
    """

    def __init__(
        self,
        twilio_ws,
        system_prompt: str,
        on_transcript_chunk: Optional[Callable[[str, str], None]] = None,
    ):
        self.twilio_ws = twilio_ws
        self.system_prompt = system_prompt
        self.on_transcript_chunk = on_transcript_chunk
        self.stream_sid: Optional[str] = None
        self.gemini_session = None
        self._stop = asyncio.Event()

    async def run(self):
        client = genai.Client(http_options={'api_version': 'v1alpha'}) # picks up GEMINI_API_KEY
        
        

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=types.Content(parts=[types.Part.from_text(text=self.system_prompt)]),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Aoede"
                    )
                )
            ),
        )

        async with client.aio.live.connect(model='gemini-2.5-flash-native-audio-latest', config=config) as session:
            self.gemini_session = session
            
            # Do NOT send any client content here.
            # The system_instruction already contains the patient persona.
            # Any send_client_content or send() call risks putting the model
            # into text-thinking mode. Let the raw audio from the phone
            # trigger VAD naturally to get a proper audio response.

            await asyncio.gather(
                self._pump_twilio_to_gemini(),
                self._pump_gemini_to_twilio(),
            )

    async def _pump_twilio_to_gemini(self):
        """Forward caller-side AGENT audio from Twilio into the model."""
        ratecv_state = None
        chunk_count = 0
        try:
            async for message in self.twilio_ws.iter_text():
                data = json.loads(message)
                event = data.get("event")

                if event == "start":
                    self.stream_sid = data["start"]["streamSid"]

                elif event == "media":
                    payload = data["media"]["payload"]  # base64 g711 ulaw
                    ulaw_bytes = base64.b64decode(payload)
                    
                    # Convert 8kHz ulaw to 8kHz pcm16
                    pcm8 = audioop.ulaw2lin(ulaw_bytes, 2)
                    # Convert 8kHz pcm16 to 16kHz pcm16 for Gemini
                    pcm16, ratecv_state = audioop.ratecv(pcm8, 2, 1, 8000, 16000, ratecv_state)
                    
                    with open("debug_gemini_input.pcm", "ab") as f:
                        f.write(pcm16)

                    chunk_count += 1
                    if chunk_count % 100 == 0:
                        print(f"[voice_bridge] twilio->gemini: sent {chunk_count} audio chunks")
                    await self.gemini_session.send_realtime_input(
                        media=types.Blob(mime_type="audio/pcm;rate=16000", data=pcm16)
                    )

                elif event == "stop":
                    self._stop.set()
                    break
        except Exception as e:
            print(f"[voice_bridge] twilio->gemini pump ended: {e}")
            self._stop.set()

    async def _pump_gemini_to_twilio(self):
        """Forward the model's synthesized audio back into the live call."""
        transcript_buffer = ""
        ratecv_state = None
        turn_count = 0
        try:
            async for message in self.gemini_session.receive():
                if self._stop.is_set():
                    break

                if not message.server_content:
                    # Log any non-server_content messages
                    attrs = [a for a in dir(message) if not a.startswith('_') and getattr(message, a) is not None]
                    print(f"[voice_bridge] non-content message: {attrs}")
                    continue

                sc = message.server_content
                mt = sc.model_turn
                tc = sc.turn_complete
                interrupted = sc.interrupted

                # --- Logging ---
                if mt:
                    has_audio = any(p.inline_data for p in mt.parts)
                    has_text = any(p.text for p in mt.parts)
                    audio_bytes = sum(len(p.inline_data.data) for p in mt.parts if p.inline_data)
                    print(f"[voice_bridge] model_turn: has_audio={has_audio}({audio_bytes}B) has_text={has_text} parts={len(mt.parts)}")
                if tc:
                    turn_count += 1
                    print(f"[voice_bridge] turn_complete (turn #{turn_count})")
                if interrupted:
                    print(f"[voice_bridge] INTERRUPTED")

                # --- Forward audio to Twilio ---
                if mt:
                    for part in mt.parts:
                        if part.inline_data:
                            pcm24 = part.inline_data.data
                            if self.stream_sid and pcm24:
                                pcm8, ratecv_state = audioop.ratecv(pcm24, 2, 1, 24000, 8000, ratecv_state)
                                ulaw_bytes = audioop.lin2ulaw(pcm8, 2)
                                out_payload = base64.b64encode(ulaw_bytes).decode("utf-8")
                                await self.twilio_ws.send_text(json.dumps({
                                    "event": "media",
                                    "streamSid": self.stream_sid,
                                    "media": {"payload": out_payload},
                                }))
                        if part.text:
                            transcript_buffer += part.text

                # --- Handle turn boundaries ---
                if tc:
                    ratecv_state = None  # reset between turns
                    if self.on_transcript_chunk and transcript_buffer:
                        self.on_transcript_chunk("patient_bot", transcript_buffer)
                        transcript_buffer = ""

                if interrupted:
                    if self.stream_sid:
                        await self.twilio_ws.send_text(json.dumps({
                            "event": "clear",
                            "streamSid": self.stream_sid,
                        }))

        except Exception as e:
            print(f"[voice_bridge] gemini->twilio pump ended: {e}")

