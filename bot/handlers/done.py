from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from sqlalchemy import text
from db.database import AsyncSessionLocal
from bot.services.xp_service import calculate_xp, award_xp, update_streak, update_bot_xp
from bot.services.rival_service import generate_rival_response


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    today = date.today()

    async with AsyncSessionLocal() as db:
        # Get today's pending plan
        result = await db.execute(
            text("""
                SELECT id, topic, duration_min
                FROM study_plan
                WHERE user_id = :uid
                  AND scheduled_date = :today
                  AND status = 'pending'
                LIMIT 1
            """),
            {"uid": user.id, "today": today}
        )
        plan = result.fetchone()

    if not plan:
        # Check if already done today
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text("""
                    SELECT topic FROM study_plan
                    WHERE user_id = :uid
                      AND scheduled_date = :today
                      AND status = 'done'
                    LIMIT 1
                """),
                {"uid": user.id, "today": today}
            )
            done_today = result.fetchone()

        if done_today:
            await update.message.reply_text(
                f"✅ You already logged *{done_today[0]}* today!\n\n"
                f"Come back tomorrow for the next session. 💪",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "📭 No session scheduled for today.\n\n"
                "Use /plan to set up your study plan."
            )
        return

    plan_id, topic, duration_min = plan

    # Show confirmation buttons
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Full session", callback_data=f"done_full_{plan_id}_{duration_min}"),
            InlineKeyboardButton("⚡ Partial", callback_data=f"done_partial_{plan_id}_{duration_min}"),
        ]
    ])

    await update.message.reply_text(
        f"📚 Today's topic: *{topic}*\n"
        f"⏱ Planned: {duration_min // 60}h {duration_min % 60}m\n\n"
        f"Did you complete the full session or partial?",
        parse_mode="Markdown",
        reply_markup=keyboard
    )


async def done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    data = query.data.split("_")

    # data = ['done', 'full'/'partial', plan_id, planned_duration]
    session_type = data[1]
    plan_id = int(data[2])
    planned_duration = int(data[3])

    # Actual duration based on full or partial
    actual_duration = planned_duration if session_type == "full" else planned_duration // 2

    async with AsyncSessionLocal() as db:
        # Get topic name
        result = await db.execute(
            text("SELECT topic FROM study_plan WHERE id = :pid"),
            {"pid": plan_id}
        )
        row = result.fetchone()
        topic = row[0] if row else "today's topic"

        # Mark plan as done
        await db.execute(
            text("UPDATE study_plan SET status = 'done' WHERE id = :pid"),
            {"pid": plan_id}
        )

        # Log session
        xp_earned = calculate_xp(actual_duration)
        await db.execute(
            text("""
                INSERT INTO sessions (user_id, plan_id, notes, xp_earned)
                VALUES (:uid, :pid, :notes, :xp)
            """),
            {
                "uid": user.id,
                "pid": plan_id,
                "notes": f"{session_type} session",
                "xp": xp_earned
            }
        )
        await db.commit()

    # Award XP and update streak
    await award_xp(user.id, xp_earned)
    streak = await update_streak(user.id)
    bot_xp = await update_bot_xp(user.id, xp_earned)

    # Generate rival response
    rival_msg = generate_rival_response(topic, actual_duration)

    streak_text = f"🔥 Streak: {streak} day{'s' if streak != 1 else ''}" if streak else ""

    await query.edit_message_text(
        f"✅ *{topic}* logged!\n\n"
        f"⚡ +{xp_earned} XP earned\n"
        f"{streak_text}\n\n"
        f"*Studybot says:*\n_{rival_msg}_",
        parse_mode="Markdown"
    )


def get_done_handler():
    return [
        CommandHandler("done", done),
        CallbackQueryHandler(done_callback, pattern="^done_"),
    ]
