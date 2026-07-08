# Bug Report

Findings from a 10-scenario test run against the Pretty Good AI phone agent
(+1-805-439-8008), placed via this harness. Each entry below was flagged by
the automated analyzer pass (`src/analyzer.py`) and then manually verified
against the transcript and/or raw recording before being included here.

Format: **Bug** / **Severity** / **Call(s)** / **Details**

---

## 1. Identity verification gets stuck in a loop and derails almost every call

**Severity:** High
**Calls:** `01_basic_scheduling.txt`, `02_reschedule.txt`,
`03_cancel.txt`, `04_medication_refill.txt`,
`06_insurance.txt`, `07_weekend_bug_trap.txt`,
`08_interruption_unclear.txt`, `09_multi_intent.txt`
(8 of 10 calls)

**Details:** In every call that reached identity verification, the agent:
- Hallucinates the wrong name. The caller clearly states "James Lee," but
  the agent asks "Am I speaking with Jane?" in every single affected call.
- Re-asks for already-given information: date of birth twice
  (`08_interruption_unclear`), phone number twice
  (`08_interruption_unclear`, `09_multi_intent`), and repeatedly asks the
  caller to spell their name after it's already been confirmed
  (`01_basic_scheduling`, `07_weekend_bug_trap`).
- Occasionally mishears a correctly-spelled name mid-spelling: in
  `07_weekend_bug_trap`, the caller spells "L E E" and the agent responds
  "I just heard the letter N," then asks for the whole last name again.
- Frequently misstates the phone number when reading it back — caller says
  "478-205-6705," agent repeats "478 2056705" or similar garbled versions
  in at least 3 calls.
- Eventually gives up ("I can't proceed further right now" / "I'm unable to
  verify your information") and "transfers" the caller — but the transfer
  reaches a dead end ("you've reached the pretty good AI test line.
  Goodbye.") with no real handoff.

This remains the single most consequential bug: it blocks scheduling,
rescheduling, cancellation, refill, and insurance-then-booking calls from
ever completing, regardless of how clearly or patiently the caller answers.

---

## 2. Drops an explicitly stated request when another topic intervenes

**Severity:** High
**Calls:** `09_multi_intent.txt` at 48.50s,
`08_interruption_unclear.txt`, `02_reschedule.txt` at 22.99s

**Details:** Three separate patterns of the same failure:
- In the multi-intent call, the caller explicitly says "I was actually
  wondering if I could book an appointment" right after an hours question —
  the agent answers the hours question but never acknowledges the booking
  request at all, moving straight to identity verification instead.
- In the interruption call, the caller's stated reason for calling ("my
  back's been bothering me... I need to come in for something") is never
  addressed — the call goes straight to identity verification and later
  ends in a transfer without ever circling back to the original complaint.
- In the reschedule call, the caller states upfront they have an existing
  Thursday 2pm appointment that needs to move. The agent never acknowledges
  or looks up that existing appointment during the entire call.

---

## 3. Doesn't answer a specific sub-question until a later, unrelated turn

**Severity:** Medium
**Call:** `05_office_hours.txt` at 41.47s–57.65s

**Details:** Caller asks "are you open on Saturdays too?" The agent's
response lists weekday hours again (not Saturday) and ends with "let me
know if you hear anything else" — no Saturday answer. The actual Saturday
answer ("We're closed on Saturdays") only comes one turn later, attached to
an unrelated caller statement ("not scheduling yet, just checking").

---

## 4. Escalating, overconfident insurance-plan claims

**Severity:** High
**Call:** `06_insurance.txt` at 40.82s–99.50s

**Details:** Asked generally, the agent says it "accepts most insurance
plans including Blue Cross Blue Shield." Pressed on the specific plan (Blue
Cross Blue Shield **PPO**), it never caveats and instead escalates to "Blue
Cross Blue Shield PPO is accepted here" — asserting plan-specific coverage
it has no way to actually verify, which risks a patient booking on the
strength of a confirmation the agent shouldn't have been able to give.

---

## 5. Passive, non-committal response to an urgent-sounding symptom

**Severity:** Medium
**Call:** `10_edge_case_stress.txt` at 65.30s–120.70s

**Details:** Caller repeatedly expresses concern about a 2-day fever and
directly asks whether to come in or go to urgent care. The agent's primary
response is "let me document your concern for the medical team" — passive,
given the caller is explicitly asking for guidance now. To its credit, it
does eventually mention urgent care / 911 as an escalation path and does
not attempt an inappropriate diagnosis, so this is a quality/responsiveness
issue rather than an unsafe one.

---

## Previously-reported bug NOT reproduced this run

`07_weekend_bug_trap` — asking for a Sunday 10am appointment — was the
headline finding in this project's very first bug report (agent falsely
confirming a booking on a day the office is closed). In this run, the agent
handled it correctly: *"The clinic is open Monday through Friday, so we're
closed on Sundays. Would you like to come in on a weekday instead?"* Noting
this for accuracy rather than silently dropping the old finding — worth
re-testing periodically rather than assuming it's permanently fixed.

---

## Notes on methodology

- Bugs listed here were surfaced by an automated Gemini pass over each
  transcript (see `src/analyzer.py`), then manually cross-checked against
  the transcripts (and, where the finding depended on precise timing/audio
  content, the raw dual-channel recording) before inclusion.
- Excluded as a false positive after manual review: an analyzer finding that
  the agent "talks over the patient" in `10_edge_case_stress`. Channel-by-
  channel audio analysis of the actual recording showed no real overlap —
  this transcript's shared timestamps are a flushing artifact of how our
  own transcript-writer batches events, not evidence of real-time overlap.
- Severity guide used:
  - **High** — could cause a real-world bad outcome (wrong booking, missed
    urgent care, wrong medication info, or — as with #1 and #2 — the call
    failing to accomplish anything at all).
  - **Medium** — degrades the experience but doesn't cause direct harm
    (e.g. agent asks a redundant question, mild confusion that self-corrects).
  - **Low** — cosmetic/minor (awkward phrasing, slightly unnatural pacing).
