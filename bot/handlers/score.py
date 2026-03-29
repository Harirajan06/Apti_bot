from datetime import date
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from sqlalchemy import text
from db.database import AsyncSessionLocal
import os

PERSONA = os.getenv("BOT_PERSONA_NAME", "Studybot")


async def score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    async with AsyncSessionLocal() as db:
        # Get XP
        xp_result = await db.execute(
            text("SELECT total_xp, weekly_xp, bot_xp FROM xp WHERE user_id = :uid"),
            {"uid": user.id}
        )
        xp_row = xp_result.fetchone()

        # Get streaks
        streak_result = await db.execute(
            text("SELECT current_streak, longest_streak, bot_streak FROM streaks WHERE user_id = :uid"),
            {"uid": user.id}
        )
        streak_row = streak_result.fetchone()

        # Get completed sessions count
        sessions_result = await db.execute(
            text("SELECT COUNT(*) FROM sessions WHERE user_id = :uid"),
            {"uid": user.id}
        )
        total_sessions = sessions_result.scalar()

        # Get total and completed plan days
        plan_result = await db.execute(
            text("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as done
                FROM study_plan WHERE user_id = :uid
            """),
            {"uid": user.id}
        )
        plan_row = plan_result.fetchone()

        # Get exam countdown
        exam_result = await db.execute(
            text("SELECT exam_date FROM users WHERE id = :uid"),
            {"uid": user.id}
        )
        exam_row = exam_result.fetchone()

    if not xp_row:
        await update.message.reply_text("No data yet. Use /start to set up.")
        return

    total_xp, weekly_xp, bot_xp = xp_row
    current_streak, longest_streak, bot_streak = streak_row if streak_row else (0, 0, 0)
    total_days = plan_row[0] or 0
    done_days = int(plan_row[1] or 0)

    # Who's winning
    if total_xp > bot_xp:
        status = "🏆 You're winning!"
        diff = f"+{total_xp - bot_xp} XP ahead"
    elif bot_xp > total_xp:
        status = f"😤 {PERSONA} is ahead!"
        diff = f"-{bot_xp - total_xp} XP behind"
    else:
        status = "🤝 It's a tie!"
        diff = "neck and neck"

    # Exam countdown
    exam_text = ""
    if exam_row and exam_row[0]:
        days_left = (exam_row[0] - date.today()).days
        if days_left > 0:
            exam_text = f"\n📅 Exam in *{days_left} days*"
        elif days_left == 0:
            exam_text = "\n📅 *Exam is TODAY!* 🚨"

    # Progress bar
    progress = done_days / total_days if total_days > 0 else 0
    filled = int(progress * 10)
    bar = "█" * filled + "░" * (10 - filled)

    await update.message.reply_text(
        f"📊 *SCOREBOARD*\n"
        f"{'─' * 25}\n\n"
        f"{status}\n"
        f"_{diff}_\n\n"
        f"👤 *You*\n"
        f"⚡ Total XP: {total_xp}\n"
        f"📅 Weekly XP: {weekly_xp}\n"
        f"🔥 Streak: {current_streak} days\n"
        f"🏅 Best streak: {longest_streak} days\n\n"
        f"🤖 *{PERSONA}*\n"
        f"⚡ Total XP: {bot_xp}\n"
        f"🔥 Streak: {bot_streak} days\n\n"
        f"📚 *Progress*\n"
        f"`[{bar}]` {done_days}/{total_days} days\n"
        f"✅ Sessions logged: {total_sessions}"
        f"{exam_text}",
        parse_mode="Markdown"
    )


def get_score_handler():
    return CommandHandler("score", score)
