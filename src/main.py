"""
main.py — entry point.

Usage:
  # One-time: start ngrok (or similar) and export PUBLIC_BASE_URL to its https URL
  # e.g.: ngrok http 8765
  # export PUBLIC_BASE_URL=https://abcd1234.ngrok.io
  # export TWILIO_ACCOUNT_SID=...
  # (see .env.example)

  # Run a single scenario:
  python src/main.py call --scenario 01_basic_scheduling

  # Or run every scenario back-to-back (the standard 10-call test run):
  python src/main.py call-all

  # After calls are done, generate the bug report:
  python src/main.py analyze
"""

import argparse
import asyncio
import os
import sys
import threading
import time

from dotenv import load_dotenv

load_dotenv()

from scenarios import SCENARIOS, get_scenario, all_scenario_ids
from call_manager import CallSession, start_media_server
from analyzer import run_full_analysis


def require_env(*names):
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}")
        print("Copy .env.example to .env and fill these in.")
        sys.exit(1)


def _start_server_bg(port: int):
    require_env("GEMINI_API_KEY")
    print(f"Starting media stream server on port {port} in background...")
    t = threading.Thread(target=start_media_server, args=(port,), daemon=True)
    t.start()
    time.sleep(2)  # Give uvicorn a moment to bind


async def _run_one_call(scenario_id: str):
    require_env(
        "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_NUMBER",
        "TARGET_NUMBER", "PUBLIC_BASE_URL", "GEMINI_API_KEY",
    )
    scenario = get_scenario(scenario_id)
    session = CallSession(
        scenario=scenario,
        twilio_number=os.environ["TWILIO_NUMBER"],
        target_number=os.environ["TARGET_NUMBER"],
        public_base_url=os.environ["PUBLIC_BASE_URL"],
    )
    print(f"\n=== Calling for scenario: {scenario.name} ({scenario.id}) ===")
    record = await session.run()
    print(f"Call finished. status={record['final_status']} "
          f"duration={record.get('duration_sec')}s "
          f"transcript={record.get('transcript_path')} "
          f"recording={record.get('recording_path')}")
    return record


def cmd_call(args):
    _start_server_bg(args.port)
    asyncio.run(_run_one_call(args.scenario))


def cmd_call_all(args):
    _start_server_bg(args.port)
    for scenario_id in all_scenario_ids():
        asyncio.run(_run_one_call(scenario_id))
        # Small gap between calls so Twilio/OpenAI resources fully release.
        time.sleep(5)
    print(f"\nAll {len(SCENARIOS)} scenario calls complete. "
          f"Run `python src/main.py analyze` next.")


def cmd_analyze(args):
    require_env("GEMINI_API_KEY")
    run_full_analysis()


def build_parser():
    parser = argparse.ArgumentParser(description="Voice bot QA harness")
    sub = parser.add_subparsers(dest="command", required=True)

    p_call = sub.add_parser("call", help="Place a single test call for one scenario")
    p_call.add_argument("--scenario", required=True, choices=all_scenario_ids())
    p_call.add_argument("--port", type=int, default=8765)
    p_call.set_defaults(func=cmd_call)

    p_call_all = sub.add_parser("call-all", help="Run all scenarios sequentially (the standard 10-call run)")
    p_call_all.add_argument("--port", type=int, default=8765)
    p_call_all.set_defaults(func=cmd_call_all)

    p_analyze = sub.add_parser("analyze", help="Run the bug-finding pass over all saved transcripts")
    p_analyze.set_defaults(func=cmd_analyze)

    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)

