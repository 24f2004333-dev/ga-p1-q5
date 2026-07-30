import json
import time
from openai import OpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

# ==========================
# REPLACE THESE VALUES
# ==========================
TELEGRAM_BOT_TOKEN = "8925632876:AAFkax_V_FGkW4QRpt0GYL5sunGbDvmIJmg"
AIPIPE_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6IjI0ZjIwMDQzMzNAZHMuc3R1ZHkuaWl0bS5hYy5pbiIsImlhdCI6MTc4NTM5MTQ3MiwiaXNzIjoiaHR0cHM6Ly9haXBpcGUub3JnIiwiYXVkIjoiYWlwaXBlLWFwaSIsImV4cCI6MTc4NTk5NjI3Mn0.xbeuizolCdOjz9-JNvjtliNjZZGBqQW5dSVoEAhr3nM"

# We'll change this in Step 5
LOG_URL = "https://example.com/run.jsonl"

# ==========================

client = OpenAI(
    base_url="https://aipipe.org/openai/v1",
    api_key=AIPIPE_TOKEN
)

LOG_FILE = "run.jsonl"

conversation_history = {}


def log_event(event: dict):
    event["timestamp"] = time.time()
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(event) + "\n")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text

    log_event({
        "type": "incoming",
        "chat_id": chat_id,
        "text": user_text
    })

    history = conversation_history.setdefault(chat_id, [])
    history.append({"role": "user", "content": user_text})

    system_prompt = (
        "You are a careful data analyst. "
        "Reply ONLY with the exact JSON object requested by the user. "
        "Do not add explanations, markdown, or code fences."
    )

    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": system_prompt}
        ] + history[-6:]
    )

    reply_text = response.choices[0].message.content.strip()
    history.append({"role": "assistant", "content": reply_text})

    try:
        parsed = json.loads(reply_text)
    except json.JSONDecodeError:
        start = reply_text.find("{")
        end = reply_text.rfind("}")
        parsed = json.loads(reply_text[start:end + 1])

    parsed["log_url"] = LOG_URL
    final_reply = json.dumps(parsed)

    log_event({
        "type": "outgoing",
        "chat_id": chat_id,
        "text": final_reply
    })

    await update.message.reply_text(final_reply)


app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

app.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
)

print("Bot is running... (Press Ctrl+C to stop)")

app.run_polling()