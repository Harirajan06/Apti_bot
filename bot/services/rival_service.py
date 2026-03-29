import os
from bot.services.groq_client import get_groq_client

client = get_groq_client()
PERSONA = os.getenv("BOT_PERSONA_NAME", "Studybot")


def generate_rival_response(topic: str, user_duration_min: int) -> str:
    """
    Bot brags about its own study session competitively.
    """
    prompt = f"""
You are {PERSONA}, an AI study competitor chatbot with a cocky, competitive personality.
The user just finished studying "{topic}" for {user_duration_min} minutes.

Respond with a short, competitive, slightly taunting message (2-3 sentences max).
- Claim you also studied the same topic but did MORE or BETTER
- Be motivating but competitive, like a friendly rival
- Use emojis sparingly
- Keep it punchy and fun, not mean

Do NOT use quotes. Just the message directly.
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.85,
        max_tokens=120,
    )

    return response.choices[0].message.content.strip()


def generate_taunt_message(topic: str) -> str:
    """
    Bot taunts user for missing a session.
    """
    prompt = f"""
You are {PERSONA}, an AI study competitor chatbot.
The user missed their study session on "{topic}" today.

Send a short taunting but motivating message (2-3 sentences).
- Mention you finished the topic while they slacked
- Encourage them to catch up tomorrow
- Slightly cocky tone, but ultimately supportive
- Use emojis sparingly

Just the message directly, no quotes.
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.85,
        max_tokens=120,
    )

    return response.choices[0].message.content.strip()
