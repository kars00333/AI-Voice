# Architecture

This bot places outbound calls via Twilio to the test line and bridges the live call
audio directly to Google Gemini's Live API (speech-to-speech), rather than chaining
separate STT → LLM → TTS services. A chained pipeline adds the latency of three
sequential network round-trips per conversational turn, which tends to produce the
multi-second dead-air pauses that make a voice bot sound obviously artificial — a
specific rejection risk called out in the challenge brief. Keeping audio-in →
audio-out in one streaming session (`src/voice_bridge.py`) was the architecture we
were confident could hit natural turn-taking pacing within the build's time budget.
Getting that pacing actually right took real iteration: the model's own voice
activity detection needed explicit tuning (sensitivity + a 1.5s silence threshold)
to stop it from either barging in mid-sentence or sitting on long pauses, its
opening line has to wait out the practice line's own answering disclaimer before
speaking, and its "thinking" mode has to be disabled outright or it burns time
reasoning in text before ever producing audio.

Each of the scenarios in `src/scenarios.py` is defined as a goal + a set of
persona traits, not a scripted line-by-line script — the system prompt tells the
model who it's pretending to be and what it's trying to accomplish, and it
improvises the actual wording each call. This was a deliberate choice to satisfy
the brief's requirement that the caller "behave like a real user interacting with
a production voice agent, not a scripted benchmark runner." The caller's identity
(name, DOB, phone number) is fixed rather than improvised per call, so identity-
verification flows are testable and reproducible across runs instead of varying
call to call. `call_manager.py` owns the Twilio call lifecycle (placing the call,
starting dual-channel recording, running a small FastAPI websocket server that
Twilio's Media Stream connects to) and assembles the transcript live from Gemini's
own input/output transcription channels, tagging each line by speaker. After all
calls complete, `analyzer.py` runs a second Gemini pass over each transcript
looking for specific failure patterns (wrong commitments, hallucinated policy,
mishandled interruptions, etc.), producing a draft bug report that we then
manually reviewed and cross-checked against the recordings before finalizing
`reports/BUG_REPORT.md`.
