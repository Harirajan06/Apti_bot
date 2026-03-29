import re
import random
import os
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ─── Time Parser ─────────────────────────────────────────────────
def parse_duration(text: str) -> int | None:
    text = text.strip().lower()
    total_seconds = 0
    matched = False

    hour_match = re.search(r'(\d+)h', text)
    min_match  = re.search(r'(\d+)m', text)
    sec_match  = re.search(r'(\d+)s', text)

    if hour_match:
        total_seconds += int(hour_match.group(1)) * 3600
        matched = True
    if min_match:
        total_seconds += int(min_match.group(1)) * 60
        matched = True
    if sec_match:
        total_seconds += int(sec_match.group(1))
        matched = True

    if not matched or total_seconds <= 0:
        return None
    if total_seconds > 7200:
        return None

    return total_seconds


def format_duration(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    parts = []
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    if s: parts.append(f"{s}s")
    return " ".join(parts)


# ─── Aptitude Question Generator ─────────────────────────────────
def generate_aptitude_question() -> str:
    topics = [
        "Time and Work",
        "Speed, Distance and Time",
        "Profit and Loss",
        "Simple Interest",
        "Compound Interest",
        "Percentages",
        "Ratio and Proportion",
        "Pipes and Cisterns",
        "Ages",
        "Averages",
    ]
    topic = random.choice(topics)

    prompt = f"""
Generate one aptitude question on the topic: "{topic}"

Format EXACTLY like this, nothing else:

📐 TOPIC: {topic}

🔢 FORMULA:
<the key formula>

❓ QUESTION:
<one clear question>

✅ SOLUTION:
<step by step solution with final answer>

Keep it short. Max 3 steps in solution.
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=300,
    )

    return response.choices[0].message.content.strip()


# ─── Timer Done ───────────────────────────────────────────────────
async def timer_done(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    user_id = job.data["user_id"]
    duration_text = job.data["duration_text"]

    try:
        aptitude = generate_aptitude_question()
    except Exception as e:
        print(f"Aptitude generation error: {e}")
        aptitude = "📐 Try an aptitude problem from your textbook!"

    await context.bot.send_message(
        chat_id=user_id,
        text=(
            f"⏰ *Time's up! {duration_text} complete!*\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🧠 *APTITUDE CHALLENGE*\n"
            f"Solve this on your break:\n\n"
            f"{aptitude}\n"
            f"━━━━━━━━━━━━━━━━━━━"
        ),
        parse_mode="Markdown"
    )


# ─── Detect Shorthand ────────────────────────────────────────────
async def detect_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text_input = update.message.text.strip()

    # Handle stop
    if text_input.lower() == "stop":
        jobs = context.application.job_queue.get_jobs_by_name(
            f"timer_{update.effective_user.id}"
        )
        if jobs:
            for job in jobs:
                job.schedule_removal()
            await update.message.reply_text("⏹ Timer stopped.")
        else:
            await update.message.reply_text("No active timer.")
        return

    seconds = parse_duration(text_input)
    if seconds is None:
        return

    user_id = update.effective_user.id
    duration_text = format_duration(seconds)

    # Cancel any existing timer
    existing = context.application.job_queue.get_jobs_by_name(f"timer_{user_id}")
    for job in existing:
        job.schedule_removal()

    # Schedule timer
    context.application.job_queue.run_once(
        timer_done,
        when=seconds,
        data={"user_id": user_id, "duration_text": duration_text},
        name=f"timer_{user_id}"
    )

    await update.message.reply_text(
        f"✅ *Timer set for {duration_text}!*\n\n"
        f"📵 Focus up — aptitude question coming when time's up.\n"
        f"Send `stop` to cancel.",
        parse_mode="Markdown"
    )


# ─── /start guide ────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⏱ *Study Timer Bot*\n\n"
        "Just send the duration to start a timer:\n\n"
        "`25m` → 25 minutes\n"
        "`40s` → 40 seconds\n"
        "`1h` → 1 hour\n"
        "`1h30m` → 1 hour 30 minutes\n"
        "`45m30s` → 45 min 30 sec\n\n"
        "When done you get a 🧠 aptitude problem to solve on your break.\n\n"
        "Send `stop` to cancel a running timer.",
        parse_mode="Markdown"
    )


def get_pomodoro_handler():
    return [
        CommandHandler("start", start),
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            detect_timer
        ),
    ]
