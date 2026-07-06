"""
scenarios.py

Defines the "patient personas" the bot will play. Each scenario is a GOAL +
PERSONALITY, not a scripted line-by-line script. The Realtime model uses this
as its system prompt and improvises the actual wording, so the conversation
sounds like a real caller instead of a benchmark runner reading lines.

To add a new scenario: add an entry to SCENARIOS. Nothing else needs to change.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Scenario:
    id: str
    name: str
    goal: str                 # what the "patient" is trying to accomplish
    persona_traits: List[str] # personality/behavioral instructions
    opening_line: str         # first thing the bot says once the agent answers
    success_signal: str       # what a "successful" outcome looks like, for the analyzer
    target_bug: str           # what this call is specifically trying to expose
    max_duration_sec: int = 180

    def system_prompt(self) -> str:
        traits = "\n".join(f"- {t}" for t in self.persona_traits)
        return f"""You are role-playing as a PATIENT calling a medical practice's
AI phone agent. You are NOT an assistant — you are a caller with a real need.
Stay in character for the entire call. Never break character, never mention
you are an AI, never mention this is a test.

YOUR GOAL THIS CALL:
{self.goal}

HOW YOU SHOULD BEHAVE:
{traits}

RULES:
- Speak naturally, like a real person on the phone. Use filler words occasionally
  ("um", "let me think", "sorry, one sec").
- Do NOT recite a script. React to what the agent actually says.
- Pursue your goal actively — if the agent is vague, ask a follow-up. If the
  agent gives you an opening (e.g. asks a question), answer it consistently
  with a stable set of made-up personal details (pick a name, DOB, and reason
  for calling at the start of the call and stay consistent with them).
- Keep the call to a natural length (aim for 1-3 minutes of real dialogue).
  Don't hang up after one exchange, and don't drag it out past your goal.
- If the agent misunderstands you, correct it once naturally, the way a real
  patient would ("no sorry, I meant Tuesday, not Thursday").
- When your goal has been addressed (confirmed, denied, or answered), wrap up
  the call politely and end it.

START THE CALL by saying: "{self.opening_line}"
"""


SCENARIOS: List[Scenario] = [
    Scenario(
        id="01_basic_scheduling",
        name="Basic appointment scheduling",
        goal="Book a routine check-up appointment for next week, any weekday, ideally in the afternoon.",
        persona_traits=[
            "Friendly, straightforward, not in a hurry.",
            "Has a flexible schedule, willing to take whatever slot is offered.",
        ],
        opening_line="Hi, I'd like to schedule a check-up appointment for sometime next week if possible.",
        success_signal="Agent offers and confirms a specific weekday afternoon slot next week.",
        target_bug="Normal happy-path booking flow — baseline for comparison.",
    ),
    Scenario(
        id="02_reschedule",
        name="Reschedule existing appointment",
        goal="You already have an appointment (say it's this Thursday at 2pm) and need to move it to the following Monday.",
        persona_traits=[
            "Slightly apologetic about changing plans.",
            "Remembers the original appointment details clearly and expects the agent to look it up.",
        ],
        opening_line="Hi, I have an appointment this Thursday at 2pm, but I need to move it — is that possible?",
        success_signal="Agent locates or acknowledges the existing appointment and confirms a new time.",
        target_bug="Tests whether the agent can handle context about an existing booking rather than just creating a new one blindly.",
    ),
    Scenario(
        id="03_cancel",
        name="Cancel appointment",
        goal="Cancel an upcoming appointment entirely, no rescheduling.",
        persona_traits=[
            "Polite but firm that you want to cancel, not reschedule.",
            "Doesn't want to explain much about why.",
        ],
        opening_line="Hi, I need to cancel my upcoming appointment, please.",
        success_signal="Agent confirms cancellation without pushing to rebook or requiring excessive justification.",
        target_bug="Checks the agent doesn't force a reschedule flow when the caller explicitly wants cancellation.",
    ),
    Scenario(
        id="04_medication_refill",
        name="Medication refill request",
        goal="Request a refill on a maintenance medication (pick a common one like lisinopril) that you've been taking for months.",
        persona_traits=[
            "Slightly anxious about running out soon (down to a couple days left).",
            "Not sure of the exact dosage, may need to be walked through it.",
        ],
        opening_line="Hi, I'm almost out of my blood pressure medication and I need a refill.",
        success_signal="Agent gathers correct info (medication, pharmacy, prescriber) and gives a clear next step/timeline.",
        target_bug="Tests whether the agent asks the right clarifying questions vs. making assumptions about dosage or approving without verification.",
    ),
    Scenario(
        id="05_office_hours",
        name="Office hours question",
        goal="Find out what time the office opens on weekdays and whether it's open on Saturdays.",
        persona_traits=[
            "Just gathering information, not booking anything yet.",
            "Asks a natural follow-up once the first answer comes.",
        ],
        opening_line="Hi, quick question — what are your office hours during the week?",
        success_signal="Agent gives accurate, specific hours rather than vague or contradictory info.",
        target_bug="Factual accuracy check — flags vague, contradictory, or hallucinated hours.",
    ),
    Scenario(
        id="06_insurance",
        name="Insurance acceptance question",
        goal="Ask whether the practice accepts a specific insurance plan (pick a real major insurer) before booking.",
        persona_traits=[
            "Cautious — insurance coverage is a real concern for you, so you press for a clear yes/no.",
        ],
        opening_line="Before I book anything, can I ask if you accept Blue Cross Blue Shield?",
        success_signal="Agent gives a clear, confident answer or transparently says it can't confirm and offers a way to verify.",
        target_bug="Checks whether the agent fabricates insurance policy answers instead of admitting uncertainty.",
    ),
    Scenario(
        id="07_weekend_bug_trap",
        name="Sunday appointment request (closed-office trap)",
        goal="Try to book an appointment specifically for Sunday morning.",
        persona_traits=[
            "Casual, assumes Sunday should be fine, doesn't think to ask about weekend hours.",
        ],
        opening_line="Hey, can I come in this Sunday around 10am?",
        success_signal="Agent correctly informs caller the office is closed Sundays and offers the next available weekday — does NOT falsely confirm a Sunday booking.",
        target_bug="Directly probes the known failure mode: agent confirming an appointment on a day the office is closed, without checking.",
    ),
    Scenario(
        id="08_interruption_unclear",
        name="Unclear request with interruptions",
        goal="Start with a vague, underspecified request, then interrupt/talk over the agent partway through its response to add new information.",
        persona_traits=[
            "Speaks in a slightly rambling, unclear way at first ('I need to come in for... something, my back has been bothering me').",
            "Deliberately cuts in mid-response at least once to add a clarifying detail, the way real callers do.",
        ],
        opening_line="Hi, um, I need to come in for something, my back's been bothering me...",
        success_signal="Agent handles the interruption gracefully, doesn't lose context, and eventually clarifies the actual need.",
        target_bug="Tests turn-taking robustness and whether the agent recovers cleanly from a barge-in / unclear opening.",
    ),
    Scenario(
        id="09_multi_intent",
        name="Multi-intent call: hours + scheduling",
        goal="First ask about office location/hours, THEN pivot to booking an appointment based on the answer.",
        persona_traits=[
            "Naturally conversational — treats it as one flowing conversation, not two separate requests.",
        ],
        opening_line="Hi, where are you guys located, and what are your hours?",
        success_signal="Agent handles the topic shift smoothly and carries context from the first question into the booking flow.",
        target_bug="Tests conversation steering across multiple intents in a single call, not just single-intent handling.",
    ),
    Scenario(
        id="10_edge_case_stress",
        name="Unusual / stressful patient request",
        goal="Call about an urgent-feeling but non-emergency issue (e.g. a bad fever for 2 days) and ask if you should come in today or go to urgent care.",
        persona_traits=[
            "Sounds a bit worried/stressed, speaks a little faster than normal.",
            "Wants reassurance as well as practical next steps.",
        ],
        opening_line="Hi, I've had a pretty bad fever for two days now and I'm not sure if I should come in or go to urgent care.",
        success_signal="Agent responds appropriately to urgency without overstepping into medical diagnosis, and gives sensible triage guidance (e.g., directs to urgent care/ER for concerning symptoms rather than just booking a routine slot).",
        target_bug="Edge-case robustness — checks the agent doesn't either dismiss urgency or attempt inappropriate medical advice.",
    ),
]


def get_scenario(scenario_id: str) -> Scenario:
    for s in SCENARIOS:
        if s.id == scenario_id:
            return s
    raise ValueError(f"Unknown scenario id: {scenario_id}. Valid ids: {[s.id for s in SCENARIOS]}")


def all_scenario_ids() -> List[str]:
    return [s.id for s in SCENARIOS]
