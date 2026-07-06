# Voice Bot QA Harness

Automated "patient" caller that tests Pretty Good AI's phone agent by placing real
outbound calls, holding natural voice conversations across 10 scenarios, recording +
transcribing each one, and generating a bug report.

See `ARCHITECTURE.md` for the design rationale.

## Setup

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Get accounts/keys**
   - Twilio account with a purchased phone number (this is your single outbound caller ID)
   - OpenAI API key with Realtime API access
   - Anthropic API key
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

**Terminal 1** — start the media-stream server (keep this running throughout):
```bash
python src/main.py serve
```

**Terminal 2** — place calls:
```bash
# Run a single scenario
python src/main.py call --scenario 01_basic_scheduling

# Or run the full standard set of 10 scenarios back-to-back
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

See `src/scenarios.py` for full detail. Covers: basic scheduling, reschedule, cancel,
medication refill, office hours, insurance question, a "Sunday appointment" closed-office
trap, an unclear/interruption-heavy call, a multi-intent call, and an urgent/stress
edge case.

## Notes

- Only one Twilio number is used for all test calls (`TWILIO_NUMBER` in `.env`), and all
  calls target `+18054398008` only.
- `src/transcriber.py` is an optional fallback for re-checking a recording's transcript
  independently of the live one — not required for normal operation.
