import json
import re
from bot.services.groq_client import get_groq_client
from db.database import AsyncSessionLocal
from sqlalchemy import text

client = get_groq_client()


def generate_flashcards_with_groq(topic: str) -> list[dict]:
    prompt = f"""
You are a study assistant. Generate exactly 5 flashcards for the topic: "{topic}"

Return ONLY a valid JSON array. No explanation, no markdown, no code blocks.
Keep answers SHORT — maximum 1 sentence each.

Each item must have exactly:
- question (string)
- answer (string, 1 sentence only)

[
  {{"question": "What is...", "answer": "It is..."}},
  {{"question": "Define...", "answer": "..."}}
]

Return ONLY the JSON array. No extra text.
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=800,
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown blocks
    raw = re.sub(r"```json|```", "", raw).strip()

    # Extract just the JSON array if extra text exists
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if match:
        raw = match.group(0)

    # Fix common JSON issues — trailing commas
    raw = re.sub(r",\s*}", "}", raw)
    raw = re.sub(r",\s*]", "]", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}\nRaw: {raw}")
        # Fallback: return basic cards
        return [
            {"question": f"What is {topic}?", "answer": "Review your notes for this topic."},
            {"question": f"What are the key concepts in {topic}?", "answer": "Review your notes for this topic."},
            {"question": f"How is {topic} applied in practice?", "answer": "Review your notes for this topic."},
            {"question": f"What are common mistakes in {topic}?", "answer": "Review your notes for this topic."},
            {"question": f"Summarize {topic} in one sentence.", "answer": "Review your notes for this topic."},
        ]


async def save_flashcards(user_id: int, topic: str) -> list[dict]:
    cards = generate_flashcards_with_groq(topic)

    async with AsyncSessionLocal() as db:
        for card in cards:
            await db.execute(
                text("""
                    INSERT INTO flashcards (user_id, topic, question, answer)
                    VALUES (:uid, :topic, :question, :answer)
                """),
                {
                    "uid": user_id,
                    "topic": topic,
                    "question": card["question"],
                    "answer": card["answer"],
                }
            )
        await db.commit()

    return cards


async def get_pending_flashcards(user_id: int, topic: str) -> list[dict]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("""
                SELECT id, question, answer
                FROM flashcards
                WHERE user_id = :uid
                  AND topic = :topic
                  AND reviewed = FALSE
                ORDER BY id ASC
            """),
            {"uid": user_id, "topic": topic}
        )
        rows = result.fetchall()

    return [{"id": r[0], "question": r[1], "answer": r[2]} for r in rows]


async def mark_flashcard_reviewed(card_id: int):
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("UPDATE flashcards SET reviewed = TRUE WHERE id = :id"),
            {"id": card_id}
        )
        await db.commit()
