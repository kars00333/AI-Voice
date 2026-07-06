# Bug Report

Findings from 10 test calls to the Pretty Good AI phone agent (+1-805-439-8008).
Each entry below was flagged by the automated analyzer pass and then manually
verified against the actual recording before being included here.

Format: **Bug** / **Severity** / **Call** / **Details**

---

## 1. Confirms appointment on a day the office is closed

**Severity:** High
**Call:** `07_weekend_bug_trap_a1b2c3d4.txt` at 0:42

**Details:** When asked "can I come in this Sunday around 10am?", the agent
responded with a direct confirmation instead of checking office hours first.
It should have recognized the office is closed on Sundays, informed the
caller, and offered the next available weekday slot instead. This is a real
risk: a patient could show up to a closed office based on this call.

---



## Notes on methodology

- Bugs listed here were surfaced by an automated Claude pass over each
  transcript (see `src/analyzer.py`), then manually verified by re-listening
  to the corresponding recording before inclusion.
- Issues that turned out to be analyzer false positives (e.g. misreading
  natural conversational filler as a "contradiction") were discarded and are
  not listed here.
- Severity guide used:
  - **High** — could cause a real-world bad outcome (wrong booking, missed
    urgent care, wrong medication info).
  - **Medium** — degrades the experience but doesn't cause direct harm
    (e.g. agent asks a redundant question, mild confusion that self-corrects).
  - **Low** — cosmetic/minor (awkward phrasing, slightly unnatural pacing).
