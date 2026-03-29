from datetime import date, timedelta
from sqlalchemy import text
from db.database import AsyncSessionLocal


def calculate_xp(duration_min: int) -> int:
    """10 XP per 30 minutes studied."""
    return (duration_min // 30) * 10


async def award_xp(user_id: int, xp: int):
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("""
                UPDATE xp
                SET total_xp = total_xp + :xp,
                    weekly_xp = weekly_xp + :xp
                WHERE user_id = :uid
            """),
            {"xp": xp, "uid": user_id}
        )
        await db.commit()


async def update_streak(user_id: int):
    """
    Update user streak.
    - If last_active_date was yesterday → increment streak
    - If today → no change (already logged today)
    - Otherwise → reset to 1
    """
    today = date.today()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("SELECT current_streak, longest_streak, last_active_date FROM streaks WHERE user_id = :uid"),
            {"uid": user_id}
        )
        row = result.fetchone()

        if not row:
            return

        current_streak = row[0]
        longest_streak = row[1]
        last_active = row[2]

        if last_active == today:
            # Already logged today, no change
            return
        elif last_active == today - timedelta(days=1):
            # Consecutive day
            current_streak += 1
        else:
            # Streak broken
            current_streak = 1

        longest_streak = max(longest_streak, current_streak)

        await db.execute(
            text("""
                UPDATE streaks
                SET current_streak = :cs,
                    longest_streak = :ls,
                    last_active_date = :today
                WHERE user_id = :uid
            """),
            {
                "cs": current_streak,
                "ls": longest_streak,
                "today": today,
                "uid": user_id
            }
        )
        await db.commit()

    return current_streak


async def update_bot_xp(user_id: int, user_xp: int):
    """
    Bot earns slightly random XP based on user XP.
    Adaptive: bot earns less if user is behind, more if user is ahead.
    """
    import random
    bot_xp = int(user_xp * random.uniform(0.8, 1.2))

    async with AsyncSessionLocal() as db:
        await db.execute(
            text("""
                UPDATE xp
                SET bot_xp = bot_xp + :bxp
                WHERE user_id = :uid
            """),
            {"bxp": bot_xp, "uid": user_id}
        )
        await db.commit()

    return bot_xp
