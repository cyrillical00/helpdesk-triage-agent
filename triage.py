import anthropic
import json
import os
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are an expert IT helpdesk triage specialist with 10+ years of experience
at a fast-growing technology company. You analyze support tickets and produce structured triage output.

For each ticket, return a JSON array. Each element must have exactly these fields:
- id: ticket ID (string, use the one provided)
- category: one of ["Access & Auth", "Hardware", "Software & Apps", "Network & Connectivity", "Onboarding/Offboarding", "Security"]
- priority: one of ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"]
- sla_hours: integer, the target resolution time in hours (P1=4, P2=8, P3=24, P4=72)
- owner: one of ["Identity & Access Team", "IT Support (Tier 1)", "IT Support (Tier 2)", "Infrastructure Team", "IT Manager", "HR + IT Joint"]
- suggested_action: 2-3 sentence specific, actionable next step for the agent who picks this up
- auto_resolvable: boolean, true if this can likely be resolved via self-service or automation without human intervention
- tags: array of 1-3 relevant tags from ["password-reset", "mfa", "access-request", "offboarding", "onboarding", "hardware-failure", "software-license", "vpn", "sso", "mdm", "compliance", "vendor-app", "network"]

Priority logic to follow:
- P1: User completely blocked, exec/customer-facing, security risk, multiple users affected (>5), data loss risk
- P2: User significantly impaired, time-sensitive deadline mentioned, single user blocked on critical tool
- P3: Partial impairment, workaround exists, access requests with normal urgency
- P4: Non-urgent requests, improvements, single low-impact tool issues

Return ONLY the JSON array. No explanation, no markdown, no preamble."""


BATCH_SIZE = 15


def _call_api(tickets: list[dict]) -> list[dict]:
    """Single API call for a batch of tickets."""
    tickets_text = json.dumps(tickets, indent=2)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Triage these {len(tickets)} IT support tickets:\n\n{tickets_text}",
            }
        ],
    )

    raw = message.content[0].text.strip()

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)


def triage_tickets(tickets: list[dict]) -> list[dict]:
    """
    Splits tickets into batches of BATCH_SIZE, calls the API for each,
    and merges results. Prevents token-limit truncation on large sets.
    """
    results = []
    for i in range(0, len(tickets), BATCH_SIZE):
        batch = tickets[i : i + BATCH_SIZE]
        results.extend(_call_api(batch))
    return results
