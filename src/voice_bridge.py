"""
voice_bridge.py

Bridges a live Twilio Media Stream (the phone call audio) to Gemini's Live
API (speech-to-speech). This is the "bot brain" — it receives the practice
agent's audio from the call, streams it to the model, and streams the
model's spoken response back into the call.

Why a live speech-to-speech API instead of STT -> LLM -> TTS:
  A chained pipeline adds the latency of three separate network round trips
  per turn, producing the multi-second dead air that reads as obviously
  artificial. Keeping audio-in -> audio-out in one streaming session is what
  makes the turn-taking pacing sound natural.

This module is intentionally a single-purpose bridge: it does not know
about scenarios, scoring, or file I/O beyond raw audio bytes. Higher-level
orchestration (which scenario to run, when to hang up) lives in call_manager.py.
"""

import asyncio
import base64
import json
import audioop
from typing import Optional, Callable

from google import genai
from google.genai import types

# Twilio expects outbound audio paced in real-time 20ms frames (160 bytes of
# 8kHz mono mu-law). Gemini's audio arrives in bursts (its first chunk alone
# is often ~1s), and forwarding those as oversized single "media" frames
# overruns Twilio's playback buffer into static, even though the encoding
# itself is correct — so outbound audio gets re-chunked and paced here.
TWILIO_FRAME_BYTES = 160
TWILIO_FRAME_SECONDS = 0.02

# The practice line's own answering disclaimer + greeting ("this call may be
# recorded... thanks for calling... how may I help you today?") runs
# anywhere from ~7 to ~10s depending on the exact greeting. 7.0s cut this too
# close — ground-truth audio review caught the bot starting at 0:09 while
# the agent was still mid-sentence, ending at 0:10. Padded with headroom
# above the observed worst case. This delay, plus gating real-time audio
# until the kickoff turn completes (see _gemini_audio_enabled), is what
# keeps that first exchange clean.
OPENING_LINE_DELAY_SECONDS = 10.0


class RealtimeVoiceBridge:
    """
    Manages one bridged session between a Twilio Media Stream websocket and
    the Gemini Live API websocket, for the duration of a single call.
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
        self._outbound_ulaw_buffer = bytearray()
        self._sent_frame_count = 0
        # Real-time call audio is withheld from Gemini until the opening-line
        # kickoff turn completes (see run()). The SDK itself warns that
        # interleaving send_client_content with send_realtime_input "can lead
        # to unexpected results" — in practice, the practice line's own audio
        # was independently triggering Gemini's natural VAD response before
        # our kickoff's response came back, so the bot echoed the practice's
        # greeting before saying its real opening line.
        self._gemini_audio_enabled = asyncio.Event()

    async def _send_ulaw_to_twilio(self, ulaw_bytes: bytes):
        """Queue mu-law audio and drain it to Twilio in real-time-paced 20ms
        frames, instead of forwarding whatever burst size Gemini handed us."""
        self._outbound_ulaw_buffer.extend(ulaw_bytes)
        while len(self._outbound_ulaw_buffer) >= TWILIO_FRAME_BYTES:
            frame = bytes(self._outbound_ulaw_buffer[:TWILIO_FRAME_BYTES])
            del self._outbound_ulaw_buffer[:TWILIO_FRAME_BYTES]
            payload = base64.b64encode(frame).decode("utf-8")
            await self.twilio_ws.send_text(json.dumps({
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {"payload": payload},
            }))
            self._sent_frame_count += 1
            await asyncio.sleep(TWILIO_FRAME_SECONDS)

    async def run(self):
        client = genai.Client(http_options={'api_version': 'v1alpha'})  # picks up GEMINI_API_KEY

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=types.Content(parts=[types.Part.from_text(text=self.system_prompt)]),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
                )
            ),
            # Native-audio models spend part of their turn "thinking" in text
            # even with response_modalities=["AUDIO"] — that shows up as a
            # thought-flagged text part instead of speech, and adds latency.
            # This bot only needs to speak, never reason on the page.
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            # response_modalities=["AUDIO"] means dialogue never comes back
            # as text, so the transcript comes from these two dedicated
            # transcription channels instead: output = what the bot says,
            # input = what the practice agent says (its audio is our input).
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            # Phone audio carries background noise/tones that tripped VAD's
            # start-of-speech detector and interrupted the bot's own turn —
            # LOW requires real speech, not a blip, to count as the agent
            # talking. end_of_speech_sensitivity=HIGH was tried to cut
            # response latency, but it committed to "they're done" on the
            # first brief pause, so the bot barged in mid-answer; LOW + an
            # explicit silence_duration_ms requires a real pause first.
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_LOW,
                    end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
                    silence_duration_ms=1500,
                ),
            ),
        )

        async with client.aio.live.connect(model='gemini-2.5-flash-native-audio-latest', config=config) as session:
            self.gemini_session = session

            async def _kick_off_opening_line():
                # Wait for the Twilio stream so the model's first words don't
                # get generated before there's anywhere to send them.
                while self.stream_sid is None and not self._stop.is_set():
                    await asyncio.sleep(0.05)
                if self._stop.is_set():
                    return
                await asyncio.sleep(OPENING_LINE_DELAY_SECONDS)
                if self._stop.is_set():
                    return
                # Explicitly trigger the model's first turn instead of
                # waiting on VAD from incoming call audio — otherwise the
                # first audio the model hears is the practice line's own
                # greeting, and with no signal that it's the model's turn to
                # speak, it echoes that greeting instead of its own opening
                # line. Safe now that thinking is disabled above (it wasn't,
                # before — send_client_content used to risk text-thinking
                # mode). Real-time audio is gated off until this turn
                # completes, so nothing competes with it.
                await self.gemini_session.send_client_content(
                    turns=types.Content(role="user", parts=[types.Part.from_text(
                        text="(The call has just connected. Begin speaking now.)"
                    )]),
                    turn_complete=True,
                )

            async def _audio_gate_failsafe():
                # If the kickoff turn never completes (a dropped send, a
                # stalled response), don't let the call go deaf forever —
                # fall back to normal VAD-driven audio. Must clear
                # OPENING_LINE_DELAY_SECONDS plus generation time, or this
                # fires before the kickoff even sends.
                await asyncio.sleep(OPENING_LINE_DELAY_SECONDS + 8.0)
                if not self._stop.is_set():
                    self._gemini_audio_enabled.set()

            await asyncio.gather(
                self._pump_twilio_to_gemini(),
                self._pump_gemini_to_twilio(),
                _kick_off_opening_line(),
                _audio_gate_failsafe(),
            )

    async def _pump_twilio_to_gemini(self):
        """Forward caller-side AGENT audio from Twilio into the model."""
        ratecv_state = None
        try:
            async for message in self.twilio_ws.iter_text():
                data = json.loads(message)
                event = data.get("event")

                if event == "start":
                    self.stream_sid = data["start"]["streamSid"]

                elif event == "media":
                    if not self._gemini_audio_enabled.is_set():
                        # Held back until the opening-line kickoff turn
                        # completes. Buffering-and-flushing this was tried,
                        # but forwarding several seconds of audio in one
                        # unpaced burst made it look like the agent said
                        # something and immediately went silent, so the bot
                        # jumped in again while the agent's real disclaimer
                        # was still playing live. This window only ever
                        # contains that generic disclaimer — never anything
                        # the caller needs to respond to — so dropping it is
                        # the safer choice.
                        continue

                    payload = data["media"]["payload"]  # base64 g711 ulaw
                    ulaw_bytes = base64.b64decode(payload)
                    pcm8 = audioop.ulaw2lin(ulaw_bytes, 2)  # 8kHz ulaw -> 8kHz pcm16
                    pcm16, ratecv_state = audioop.ratecv(pcm8, 2, 1, 8000, 16000, ratecv_state)  # -> 16kHz for Gemini

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
        output_transcript_buffer = ""  # what the patient bot is saying
        input_transcript_buffer = ""   # what the practice agent is saying
        ratecv_state = None
        turn_count = 0
        loop = asyncio.get_event_loop()
        last_event_at = loop.time()
        try:
            while not self._stop.is_set():
                # session.receive() is scoped to exactly one model turn — it
                # yields messages up to and including turn_complete, then its
                # generator ends by design (per the SDK's own docstring).
                # Calling it once would mean only ever hearing the bot's
                # first turn for the whole call, so this loops per-turn.
                async for message in self.gemini_session.receive():
                    now = loop.time()
                    gap = now - last_event_at
                    last_event_at = now
                    if self._stop.is_set():
                        break
                    if gap > 5.0:
                        # Confirmed via diagnostics: our own inbound audio
                        # pipe to Gemini never stops during these gaps (it
                        # keeps streaming live call audio continuously) — the
                        # delay is Gemini's own backend processing latency
                        # for this turn, not something on our side. Logged
                        # for visibility; the practice agent's own "are you
                        # still there?" retry recovers the call when this
                        # happens.
                        print(f"[voice_bridge] long gap: {gap:.1f}s before next model event")

                    if not message.server_content:
                        continue

                    sc = message.server_content
                    mt = sc.model_turn
                    tc = sc.turn_complete
                    interrupted = sc.interrupted

                    if tc:
                        turn_count += 1
                        print(f"[voice_bridge] turn_complete (turn #{turn_count})")
                        if not self._gemini_audio_enabled.is_set():
                            # Kickoff turn just finished — safe to start
                            # feeding it real call audio now.
                            self._gemini_audio_enabled.set()
                    if interrupted:
                        print("[voice_bridge] INTERRUPTED")

                    # --- Forward audio to Twilio ---
                    if mt:
                        for part in mt.parts:
                            if part.inline_data and self.stream_sid:
                                pcm24 = part.inline_data.data
                                pcm8, ratecv_state = audioop.ratecv(pcm24, 2, 1, 24000, 8000, ratecv_state)
                                ulaw_bytes = audioop.lin2ulaw(pcm8, 2)
                                await self._send_ulaw_to_twilio(ulaw_bytes)

                    # --- Transcription (its own channel, independent of
                    # model_turn/turn_complete). "finished" is the primary
                    # flush trigger; turn_complete is a fallback since it
                    # fires more consistently. Whatever's left when the pump
                    # loop ends is flushed too (see finally below), so a call
                    # cut off mid-utterance doesn't lose its tail. ---
                    if sc.output_transcription and sc.output_transcription.text:
                        output_transcript_buffer += sc.output_transcription.text
                    if sc.output_transcription and sc.output_transcription.finished and output_transcript_buffer:
                        if self.on_transcript_chunk:
                            self.on_transcript_chunk("patient_bot", output_transcript_buffer)
                        output_transcript_buffer = ""

                    if sc.input_transcription and sc.input_transcription.text:
                        input_transcript_buffer += sc.input_transcription.text
                    if sc.input_transcription and sc.input_transcription.finished and input_transcript_buffer:
                        if self.on_transcript_chunk:
                            self.on_transcript_chunk("practice_agent", input_transcript_buffer)
                        input_transcript_buffer = ""

                    if tc:
                        ratecv_state = None  # reset between turns
                        if self.on_transcript_chunk and output_transcript_buffer:
                            self.on_transcript_chunk("patient_bot", output_transcript_buffer)
                            output_transcript_buffer = ""
                        if self.on_transcript_chunk and input_transcript_buffer:
                            self.on_transcript_chunk("practice_agent", input_transcript_buffer)
                            input_transcript_buffer = ""

                    if interrupted:
                        self._outbound_ulaw_buffer.clear()
                        if self.stream_sid:
                            await self.twilio_ws.send_text(json.dumps({
                                "event": "clear",
                                "streamSid": self.stream_sid,
                            }))

        except Exception as e:
            print(f"[voice_bridge] gemini->twilio pump ended: {e}")
        finally:
            print(f"[voice_bridge] total media frames sent to Twilio: {self._sent_frame_count}")
            # Catch anything left mid-utterance when the call/stream ends
            # before a turn boundary or "finished" flag ever arrived.
            if self.on_transcript_chunk and output_transcript_buffer:
                self.on_transcript_chunk("patient_bot", output_transcript_buffer)
            if self.on_transcript_chunk and input_transcript_buffer:
                self.on_transcript_chunk("practice_agent", input_transcript_buffer)
