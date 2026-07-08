"""
analyzer.py

Runs a review pass over each call transcript looking for bugs/quality issues
in the PRACTICE AGENT's responses (never the patient bot's own lines).

This produces CANDIDATE bug entries only. Per the project plan, a human
should read and curate these before they go into reports/BUG_REPORT.md —
don't ship raw model output as your bug report.
"""

import json
import os
from pathlib import Path
from typing import List, Dict

from google import genai
from google.genai import types

REPO_ROOT = Path(__file__).resolve().parent.parent
TRANSCRIPTS_DIR = REPO_ROOT / "transcripts"
REPORTS_DIR = REPO_ROOT / "reports"

ANALYSIS_SYSTEM_PROMPT = """You are a QA reviewer for a medical-practice AI phone agent.
You will be given a call transcript between a PATIENT (a test caller) and a
PRACTICE AGENT (the system under test). Your job is to find bugs or quality
issues ONLY in the PRACTICE AGENT's behavior. Look specifically for:

- Wrong commitments (e.g. confirming an appointment on a day/time that
  shouldn't be possible, such as a closed day).
- Failure to clarify genuinely ambiguous requests.
- Contradictions or hallucinated policies (inventing hours, insurance
  coverage, or procedures it can't actually know).
- Poor interruption / turn-taking handling (talking over the caller,
  losing context after a barge-in).
- Ignoring or mishandling direct questions about hours, location,
  insurance, or refills.
- Inappropriate handling of urgent/medical situations (e.g. giving medical
  diagnosis it shouldn't, or dismissing genuine urgency).

Respond ONLY with a JSON array (no markdown, no commentary) of objects with
this exact shape:
[
  {
    "bug": "one-sentence description of the issue",
    "severity": "High" | "Medium" | "Low",
    "timestamp": "e.g. 1:23 or the [t]s marker from the transcript",
    "details": "2-4 sentences: what happened, why it's a problem, what the
                correct behavior should have been"
  }
]

If you find no issues, respond with an empty JSON array: []
"""


def analyze_transcript(client: genai.Client, transcript_path: Path) -> List[Dict]:
    transcript_text = transcript_path.read_text(encoding="utf-8")

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=transcript_text,
        config=types.GenerateContentConfig(
            system_instruction=ANALYSIS_SYSTEM_PROMPT,
            max_output_tokens=4000,
            temperature=0.0,
            # gemini-2.5-flash has "thinking" on by default, and thinking
            # tokens count against max_output_tokens — on a longer
            # transcript with several findings, that ate most of the budget
            # before the model ever got to emit the visible JSON, truncating
            # it mid-string. This is a plain extraction task, no reasoning
            # needed, so thinking is disabled outright.
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )
    )

    raw = response.text.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"[warn] could not parse analyzer output for {transcript_path.name}, "
              f"skipping automated flags for this call. Raw output saved for review.")
        (REPORTS_DIR / f"{transcript_path.stem}_raw_analysis.txt").write_text(raw)
        return []


def run_full_analysis() -> Path:
    """Analyzes every transcript in transcripts/ and writes a draft bug report."""
    client = genai.Client()
    REPORTS_DIR.mkdir(exist_ok=True)

    all_findings = []
    for transcript_path in sorted(TRANSCRIPTS_DIR.glob("*.txt")):
        findings = analyze_transcript(client, transcript_path)
        for f in findings:
            f["call"] = transcript_path.name
        all_findings.extend(findings)

    out_path = REPORTS_DIR / "BUG_REPORT_DRAFT.md"
    lines = ["# Bug Report (DRAFT — review and curate before final submission)\n"]
    if not all_findings:
        lines.append("No candidate issues flagged by automated pass. "
                      "Manually re-listen to calls before concluding there are none.")
    for f in all_findings:
        lines.append(f"## {f.get('bug', 'Untitled issue')}")
        lines.append(f"- **Severity:** {f.get('severity', 'Unknown')}")
        lines.append(f"- **Call:** {f.get('call')} at {f.get('timestamp', 'unknown time')}")
        lines.append(f"- **Details:** {f.get('details', '')}")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Draft bug report written to {out_path}")
    return out_path


if __name__ == "__main__":
    run_full_analysis()

