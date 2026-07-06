# Architecture

This bot places outbound calls via Twilio to the test line and bridges the live call
audio directly to OpenAI's Realtime API (speech-to-speech), rather than chaining
separate STT → LLM → TTS services. A chained pipeline adds the latency of three
sequential network round-trips per conversational turn, which tends to produce the
multi-second dead-air pauses that make a voice bot sound obviously artificial — a
specific rejection risk called out in the challenge brief. Keeping audio-in →
audio-out in one streaming session was the only architecture we were confident could
hit natural turn-taking pacing within the build's time budget.

Each of the 10 test scenarios (`src/scenarios.py`) is defined as a goal + a set of
persona traits, not a scripted line-by-line script — the system prompt tells the model
who it's pretending to be and what it's trying to accomplish, and it improvises the
actual wording each call. This was a deliberate choice to satisfy the brief's
requirement that the caller "behave like a real user interacting with a production
voice agent, not a scripted benchmark runner." `call_manager.py` owns the Twilio call
lifecycle (placing the call, starting dual-channel recording, running a small FastAPI
websocket server that Twilio's Media Stream connects to) and assembles the transcript
live from the Realtime API's own transcription events, tagging each line by speaker.
After all calls complete, `analyzer.py` runs a second Claude pass over each transcript
looking for specific failure patterns (wrong commitments, hallucinated policy,
mishandled interruptions, etc.), producing a draft bug report that we then manually
reviewed and curated before finalizing `reports/BUG_REPORT.md`.
