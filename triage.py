import anthropic
import json
import os
from concurrent.futures import ThreadPoolExecutor
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
- kb_id: the KB-ID (first 8 chars) of the best matching knowledge base article, or null if no match
- resolution: the exact resolution text from the matched KB article, or null if no KB match
- auto_close: boolean, true ONLY if kb_id is set AND the matched article has auto_closeable:true AND the ticket is straightforward enough to close without human intervention

Priority logic to follow:
- P1: User completely blocked, exec/customer-facing, security risk, multiple users affected (>5), data loss risk
- P2: User significantly impaired, time-sensitive deadline mentioned, single user blocked on critical tool
- P3: Partial impairment, workaround exists, access requests with normal urgency
- P4: Non-urgent requests, improvements, single low-impact tool issues

KB matching rules:
- Match based on the issue_pattern and category
- Only set kb_id if you are confident the article addresses this specific ticket
- Copy the resolution text exactly from the KB article when matched
- Set auto_close:true only for truly routine issues (account unlocks, MFA resets, simple access grants)

Return ONLY the JSON array. No explanation, no markdown, no preamble."""


BATCH_SIZE = 15


def _call_api(batch_and_kb: tuple[list[dict], str]) -> list[dict]:
    """Single API call for a batch of tickets, with KB context injected."""
    tickets, kb_block = batch_and_kb
    tickets_text = json.dumps(tickets, indent=2)

    user_content = f"Triage these {len(tickets)} IT support tickets:\n\n{tickets_text}"
    if kb_block:
        user_content = f"{kb_block}\n\n---\n\n{user_content}"

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)


def triage_tickets(tickets: list[dict], kb_block: str = "") -> list[dict]:
    """
    Splits tickets into batches and runs all batches in parallel.
    KB context is injected into each batch call.
    """
    batches = [(tickets[i : i + BATCH_SIZE], kb_block) for i in range(0, len(tickets), BATCH_SIZE)]
    with ThreadPoolExecutor(max_workers=len(batches)) as executor:
        results_per_batch = list(executor.map(_call_api, batches))
    return [item for batch in results_per_batch for item in batch]
