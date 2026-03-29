import os
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
)
from sqlalchemy import text
from db.database import AsyncSessionLocal

# Conversation states
TIMEZONE, EXAM_DATE, STUDY_PLAN = range(3)

PERSONA = os.getenv("BOT_PERSONA_NAME", "Studybot")

TIMEZONE_OPTIONS = [
    ["Asia/Kolkata", "Asia/Dubai"],
    ["Europe/London", "America/New_York"],
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Check if user already exists
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("SELECT id FROM users WHERE id = :uid"),
            {"uid": user.id}
        )
        existing = result.fetchone()

    if existing:
        await update.message.reply_text(
            f"Welcome back! Your rival *{PERSONA}* missed you 😤\n\n"
            f"Use /score to check standings or /plan to update your study plan.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"Hey {user.first_name}! 👋\n\n"
        f"I'm *{PERSONA}* — your AI study competitor.\n"
        f"You study. I study. We compete. Whoever slacks loses. 😤\n\n"
        f"Let's set you up. First — pick your timezone:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(
            TIMEZONE_OPTIONS,
            one_time_keyboard=True,
            resize_keyboard=True
        )
    )
    return TIMEZONE


async def receive_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tz = update.message.text.strip()
    valid_timezones = [t for row in TIMEZONE_OPTIONS for t in row]

    if tz not in valid_timezones:
        await update.message.reply_text(
            "Please pick one of the options from the keyboard."
        )
        return TIMEZONE

    context.user_data["timezone"] = tz

    await update.message.reply_text(
        "Got it! 🕐\n\n"
        "Now, when is your exam? Send the date in this format:\n"
        "`DD-MM-YYYY`  (e.g. 30-06-2025)\n\n"
        "If you don't have one, send `skip`.",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    return EXAM_DATE


async def receive_exam_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text_input = update.message.text.strip()
    exam_date = None

    if text_input.lower() != "skip":
        try:
            exam_date = datetime.strptime(text_input, "%d-%m-%Y").date()
        except ValueError:
            await update.message.reply_text(
                "Invalid format. Send as `DD-MM-YYYY` or send `skip`.",
                parse_mode="Markdown"
            )
            return EXAM_DATE

    context.user_data["exam_date"] = str(exam_date) if exam_date else None

    await update.message.reply_text(
        "Perfect! 📅\n\n"
        "Now send me your *study plan*. Use this format:\n\n"
        "```\n"
        "Day 1 - OS: 2 hours\n"
        "Day 2 - DBMS: 3 hours\n"
        "Day 3 - Networks: 2 hours\n"
        "```\n\n"
        "Send as many days as you want. I'll parse it automatically.",
        parse_mode="Markdown"
    )
    return STUDY_PLAN


async def receive_study_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    raw_plan = update.message.text.strip()

    if not raw_plan:
        await update.message.reply_text("Plan can't be empty. Try again.")
        return STUDY_PLAN

    # Save user to DB first
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("""
                INSERT INTO users (id, username, timezone, exam_date)
                VALUES (:id, :username, :timezone, :exam_date)
                ON DUPLICATE KEY UPDATE
                    username = :username,
                    timezone = :timezone,
                    exam_date = :exam_date
            """),
            {
                "id": user.id,
                "username": user.username or user.first_name,
                "timezone": context.user_data["timezone"],
                "exam_date": context.user_data["exam_date"],
            }
        )
        await db.execute(
            text("INSERT IGNORE INTO streaks (user_id) VALUES (:uid)"),
            {"uid": user.id}
        )
        await db.execute(
            text("INSERT IGNORE INTO xp (user_id) VALUES (:uid)"),
            {"uid": user.id}
        )
        await db.commit()

    # Tell user we're parsing
    await update.message.reply_text(
        "⏳ Parsing your plan... Studybot is loading up too 😤"
    )

    try:
        from bot.services.plan_service import save_study_plan
        parsed = await save_study_plan(user.id, raw_plan)

        # Build confirmation message
        plan_text = "\n".join([
            f"📅 Day {item['day_number']} — {item['topic']} ({item['duration_min'] // 60}h {item['duration_min'] % 60}m) → {item['scheduled_date']}"
            for item in parsed
        ])

        await update.message.reply_text(
            f"✅ Plan locked in!\n\n{plan_text}\n\n"
            f"*{PERSONA}* has the same schedule. Game on. 😤\n\n"
            f"Use /score to check standings. Use /done to log a session.",
            parse_mode="Markdown"
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Couldn't parse your plan. Try this format:\n\n"
            f"Day 1 - OS: 2 hours\n"
            f"Day 2 - DBMS: 3 hours"
        )
        print(f"Plan parse error: {e}")

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Setup cancelled. Send /start anytime to begin.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


def get_start_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            TIMEZONE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_timezone)],
            EXAM_DATE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_exam_date)],
            STUDY_PLAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_study_plan)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
