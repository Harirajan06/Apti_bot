import logging
import os
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder
from bot.handlers.pomodoro import get_pomodoro_handler

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    app = ApplicationBuilder().token(token).build()

    for handler in get_pomodoro_handler():
        app.add_handler(handler)

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()