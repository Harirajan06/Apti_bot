from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from sqlalchemy import text
from db.database import AsyncSessionLocal
from bot.services.flashcard_service import (
    save_flashcards,
    get_pending_flashcards,
    mark_flashcard_reviewed
)


async def flashcards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Get most recently completed topic
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("""
                SELECT sp.topic FROM study_plan sp
                JOIN sessions s ON s.plan_id = sp.id
                WHERE sp.user_id = :uid
                ORDER BY s.logged_at DESC
                LIMIT 1
            """),
            {"uid": user.id}
        )
        row = result.fetchone()

    if not row:
        await update.message.reply_text(
            "No completed sessions yet. Use /done to log a session first."
        )
        return

    topic = row[0]

    # Check if flashcards already exist for this topic
    existing = await get_pending_flashcards(user.id, topic)

    if not existing:
        await update.message.reply_text(
            f"⏳ Generating flashcards for *{topic}*...",
            parse_mode="Markdown"
        )
        cards = await save_flashcards(user.id, topic)
        existing = [{"id": None, "question": c["question"], "answer": c["answer"]} for c in cards]

        # Re-fetch with IDs
        existing = await get_pending_flashcards(user.id, topic)

    # Store cards in context and show first one
    context.user_data["flashcards"] = existing
    context.user_data["fc_index"] = 0
    context.user_data["fc_topic"] = topic

    await send_flashcard(update, context, is_callback=False)


async def send_flashcard(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    is_callback: bool = False
):
    cards = context.user_data.get("flashcards", [])
    index = context.user_data.get("fc_index", 0)
    topic = context.user_data.get("fc_topic", "")

    if index >= len(cards):
        text_msg = (
            f"🎉 All flashcards reviewed for *{topic}*!\n\n"
            f"Great work. Use /flashcards again after your next session."
        )
        if is_callback:
            await update.callback_query.edit_message_text(
                text_msg, parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(text_msg, parse_mode="Markdown")
        return

    card = cards[index]
    total = len(cards)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👁 Show Answer", callback_data=f"fc_show_{card['id']}")],
    ])

    text_msg = (
        f"🃏 *Flashcard {index + 1}/{total}*\n"
        f"📚 Topic: {topic}\n\n"
        f"*Q: {card['question']}*"
    )

    if is_callback:
        await update.callback_query.edit_message_text(
            text_msg,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            text_msg,
            parse_mode="Markdown",
            reply_markup=keyboard
        )


async def flashcard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("fc_show_"):
        card_id = int(data.split("_")[2])
        cards = context.user_data.get("flashcards", [])
        index = context.user_data.get("fc_index", 0)

        if index < len(cards):
            card = cards[index]
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Got it", callback_data="fc_next_got"),
                    InlineKeyboardButton("🔁 Review again", callback_data="fc_next_skip"),
                ]
            ])
            await query.edit_message_text(
                f"🃏 *Flashcard {index + 1}/{len(cards)}*\n\n"
                f"*Q: {card['question']}*\n\n"
                f"💡 *A:* {card['answer']}",
                parse_mode="Markdown",
                reply_markup=keyboard
            )

    elif data == "fc_next_got":
        # Mark reviewed and move to next
        cards = context.user_data.get("flashcards", [])
        index = context.user_data.get("fc_index", 0)
        if index < len(cards):
            await mark_flashcard_reviewed(cards[index]["id"])
        context.user_data["fc_index"] = index + 1
        await send_flashcard(update, context, is_callback=True)

    elif data == "fc_next_skip":
        # Move to next without marking reviewed
        index = context.user_data.get("fc_index", 0)
        context.user_data["fc_index"] = index + 1
        await send_flashcard(update, context, is_callback=True)


def get_flashcard_handler():
    return [
        CommandHandler("flashcards", flashcards),
        CallbackQueryHandler(flashcard_callback, pattern="^fc_"),
    ]
