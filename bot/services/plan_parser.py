import json
import re
from datetime import date, timedelta
from bot.services.groq_client import get_groq_client

client = get_groq_client()

def parse_plan_with_groq(raw_plan: str) -> list[dict]:
    """
    Send raw plan text to Groq, get back structured JSON.
    Returns list of dicts: [{day_number, topic, duration_min}]
    """
    prompt = f"""
You are a study plan parser. The user has sent their study plan in natural language.
Extract and return ONLY a valid JSON array. No explanation, no markdown, no code blocks.

Each item must have exactly these fields:
- day_number (integer)
- topic (string)
- duration_min (integer, convert hours to minutes)

Example output:
[
  {{"day_number": 1, "topic": "Operating Systems", "duration_min": 120}},
  {{"day_number": 2, "topic": "DBMS", "duration_min": 180}}
]

User's plan:
{raw_plan}

Return ONLY the JSON array. Nothing else.
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown code blocks if Groq wraps it anyway
    raw = re.sub(r"```json|```", "", raw).strip()

    parsed = json.loads(raw)
    return parsed


def assign_dates(parsed_plan: list[dict], start_date: date = None) -> list[dict]:
    """
    Assign a real calendar date to each day in the plan.
    Starts from today by default.
    """
    if start_date is None:
        start_date = date.today()

    for item in parsed_plan:
        item["scheduled_date"] = str(
            start_date + timedelta(days=item["day_number"] - 1)
        )
    return parsed_plan
