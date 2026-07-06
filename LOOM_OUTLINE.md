# Loom Walkthrough — Talking Points (target: under 5 minutes)

Goal: show how you think, not just what you built. Reviewers said this is one of the
most important deliverables. Keep it tight — script the beats below, don't ad-lib the
whole thing.

---

## 0:00–0:30 — What you built (30 sec)
- "This is an automated voice bot that calls Pretty Good AI's test line, plays a
  realistic patient across 10 different scenarios, and produces recordings,
  transcripts, and a bug report."
- One sentence on scope: "Built with Twilio for telephony and OpenAI's Realtime API
  for the actual conversation."

## 0:30–1:30 — The key architecture decision (60 sec)
- Show the layer table or `ARCHITECTURE.md` briefly on screen.
- Explain the STT→LLM→TTS vs. Realtime API tradeoff in your own words:
  "My first instinct was to chain speech-to-text, an LLM, and text-to-speech, but
  that stacks up latency — you get multi-second dead air between turns, which is
  exactly what the brief flags as a rejection risk. Switching to a single
  speech-to-speech Realtime session got turn latency down to something that
  actually sounds like a phone call."
- If you actually hit this problem during build, say so — this is your "evidence of
  iteration" moment, make it concrete rather than hypothetical.

## 1:30–2:30 — Persona design (60 sec)
- Open `scenarios.py`, show one scenario definition.
- "Instead of scripting exact lines, each scenario is a goal plus a set of
  personality traits — the model improvises the actual wording each call, which is
  why it doesn't sound like a benchmark script reading questions at the agent."
- Briefly name 2-3 of the 10 scenarios and why they're interesting (e.g. the Sunday
  closed-office trap, the interruption/barge-in test).

## 2:30–3:30 — Play a real call clip
- Cue up your best (or most interesting-bug) recording. Play 20-30 seconds of actual
  audio — this is the single most convincing thing you can show. Pick a moment where
  the conversation flows naturally AND/OR where you can point out the bug live.
- "Here's the Sunday call — listen to this part, it confirms the appointment without
  ever checking that we're closed weekends."

## 3:30–4:15 — Bug report + analysis pipeline
- Show `BUG_REPORT.md` and briefly the analyzer flow: "After each call, I run the
  transcript through a second Claude pass that flags candidate issues, but I don't
  ship that raw — I manually verify each one against the recording before it goes in
  the report, so what's here is confirmed."

## 4:15–4:45 — What you'd do with more time
- Show self-awareness on limits: e.g. "With more time I'd add automatic retries for
  dropped calls, and test more accent/pacing variation to stress the agent's ASR."

## 4:45–5:00 — Close
- "All code, transcripts, recordings, and the bug report are in the repo — thanks
  for watching."

---

## Separate recording: AI-assisted debugging (also max 5 min)

This is a **second, separate** recording. Requirements: show you actually prompting
an AI assistant to debug/fix your code, with the prompts visible on screen.

Suggested structure:
1. Pick one real bug you hit during build (e.g. a latency issue, a transcript
   speaker-attribution mixup, a Twilio recording fetch failing).
2. Show the actual error/symptom first (a failed call, garbled audio, an exception).
3. Show your actual prompt to Claude/the assistant describing the problem.
4. Show the fix it proposed, and you applying it.
5. Show the re-run confirming it's fixed.

Don't fabricate a bug for the recording — use a real one from your build process.
If you kept notes or chat history from when you built this, that's your source
material; do this recording during/after actual debugging rather than staging it
after the fact.
