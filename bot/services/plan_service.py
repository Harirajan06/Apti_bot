from datetime import date
from sqlalchemy import text
from db.database import AsyncSessionLocal
from bot.services.plan_parser import parse_plan_with_groq, assign_dates


async def save_study_plan(user_id: int, raw_plan: str) -> list[dict]:
    """
    Parse raw plan text with Groq and save to study_plan table.
    Returns the parsed plan list.
    """
    # Parse with Groq
    parsed = parse_plan_with_groq(raw_plan)

    # Assign calendar dates starting from today
    parsed = assign_dates(parsed)

    async with AsyncSessionLocal() as db:
        # Clear any existing plan for this user
        await db.execute(
            text("DELETE FROM study_plan WHERE user_id = :uid"),
            {"uid": user_id}
        )

        # Insert new plan rows
        for item in parsed:
            await db.execute(
                text("""
                    INSERT INTO study_plan 
                        (user_id, day_number, topic, duration_min, scheduled_date, status)
                    VALUES 
                        (:user_id, :day_number, :topic, :duration_min, :scheduled_date, 'pending')
                """),
                {
                    "user_id": user_id,
                    "day_number": item["day_number"],
                    "topic": item["topic"],
                    "duration_min": item["duration_min"],
                    "scheduled_date": item["scheduled_date"],
                }
            )

        await db.commit()

    return parsed
