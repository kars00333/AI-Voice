# Voice Bot QA Harness

Automated "patient" caller that tests Pretty Good AI's phone agent by placing real
outbound calls, holding natural voice conversations across 13 scenarios, recording +
transcribing each one, and generating a bug report.

See `ARCHITECTURE.md` for the design rationale.

## Setup

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Get accounts/keys**
   - Twilio account with a purchased phone number (this is your single outbound caller ID)
   - Google Gemini API key ([aistudio.google.com](https://aistudio.google.com)) — used for both
     the live voice bridge and the post-call bug analysis
   - [ngrok](https://ngrok.com) (or similar) for a public HTTPS tunnel to your local machine

3. **Configure environment**
   ```bash
   cp .env.example .env
   # fill in all values in .env
   ```

4. **Start a tunnel** (in its own terminal, keep running)
   ```bash
   ngrok http 8765
   ```
   Copy the `https://...ngrok.io` URL it prints into `.env` as `PUBLIC_BASE_URL`.

## Run

Each call starts its own local media-stream server in the background — no separate
process to manage.

```bash
# Run a single scenario
python src/main.py call --scenario 01_basic_scheduling

# Or run every scenario back-to-back
python src/main.py call-all
```

**After calls finish** — generate the draft bug report:
```bash
python src/main.py analyze
```
This writes `reports/BUG_REPORT_DRAFT.md`. Review and curate it into
`reports/BUG_REPORT.md` before submitting — don't ship the raw automated output as-is.

## Output

- `recordings/*.mp3` — call audio (dual-channel)
- `transcripts/*.txt` — speaker-tagged transcript per call
- `transcripts/*.json` — call metadata (scenario, duration, status, timestamps)
- `reports/BUG_REPORT_DRAFT.md` — automated candidate findings
- `reports/BUG_REPORT.md` — final, human-curated bug report (create this from the draft)

## Scenarios covered

See `src/scenarios.py` for full detail.

Core set: basic scheduling, reschedule, cancel, medication refill, office hours,
insurance question, a "Sunday appointment" closed-office trap, an
unclear/interruption-heavy call, a multi-intent call, and an urgent/stress edge case.

Additional: rescheduling without remembering the exact original appointment,
an identity-verification consistency check, and a new-patient intake call.

## Notes

- Only one Twilio number is used for all test calls (`TWILIO_NUMBER` in `.env`), and all
  calls target `+18054398008` only.
- The caller's identity (name, date of birth, phone number) is fixed in
  `src/scenarios.py` rather than improvised per call, so identity-verification
  behavior is consistent and reproducible across runs.
- `src/transcriber.py` is an optional fallback for re-checking a recording's transcript
  independently of the live one — not required for normal operation.
