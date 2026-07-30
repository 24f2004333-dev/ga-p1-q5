import os
import json
import time
import threading
import requests

from fastapi import FastAPI
from openai import OpenAI
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)
import uvicorn

# ==========================
# Environment variables
# ==========================

BOT_TOKEN = os.environ["BOT_TOKEN"]
AIPIPE_TOKEN = os.environ["AIPIPE_TOKEN"]
BASE_URL = os.environ.get("BASE_URL", "")
LOG_URL = os.environ.get(
    "LOG_URL",
    "https://raw.githubusercontent.com/24f2004333-dev/ga-p1-q5/main/run.jsonl",
)

LOG_FILE = "run.jsonl"

client = OpenAI(
    base_url="https://aipipe.org/openai/v1",
    api_key=AIPIPE_TOKEN,
)

conversation_history = {}

app = FastAPI()


@app.get("/")
def root():
    return {"status": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}


def log_event(event):
    event["timestamp"] = time.time()
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(event) + "\n")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text

    log_event(
        {
            "type": "incoming",
            "chat_id": chat_id,
            "text": user_text,
        }
    )

    history = conversation_history.setdefault(chat_id, [])

    history.append(
        {
            "role": "user",
            "content": user_text,
        }
    )

    system_prompt = (
        "You are a careful data analyst. "
        "Reply ONLY with the exact JSON object requested by the user. "
        "Do not add markdown or explanations."
    )

    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            }
        ]
        + history[-6:],
    )

    reply = response.choices[0].message.content.strip()

    history.append(
        {
            "role": "assistant",
            "content": reply,
        }
    )

    try:
        parsed = json.loads(reply)
    except Exception:
        start = reply.find("{")
        end = reply.rfind("}")
        parsed = json.loads(reply[start : end + 1])

    parsed["log_url"] = LOG_URL

    final_reply = json.dumps(parsed)

    log_event(
        {
            "type": "outgoing",
            "chat_id": chat_id,
            "text": final_reply,
        }
    )

    await update.message.reply_text(final_reply)


telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

telegram_app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message,
    )
)


async def start_bot():
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.updater.start_polling()


@app.on_event("startup")
async def startup():
    await start_bot()


def self_ping():
    if not BASE_URL:
        return

    while True:
        time.sleep(600)

        try:
            requests.get(
                f"{BASE_URL}/health",
                timeout=10,
            )
        except Exception:
            pass


threading.Thread(
    target=self_ping,
    daemon=True,
).start()


if __name__ == "__main__":
    uvicorn.run(
        "bot:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
    )