# Study Rival Bot

Telegram study rival bot with Groq-powered plan parsing, XP, and streaks.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```dotenv
TELEGRAM_BOT_TOKEN=your_token_here
GROQ_API_KEY=your_groq_api_key_here
LLM_MODEL=llama-3.1-8b-instant
STT_MODEL=whisper-large-v3-turbo
DATABASE_URL=mysql+aiomysql://user:password@localhost/studyrival
BOT_PERSONA_NAME=Studybot
BOT_USERNAME=@HabitSensaiBot
```

## Run

```bash
python main.py
```
