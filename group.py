from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # or paste your token here

print(BOT_TOKEN)

async def any_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat:
        print("Chat title:", chat.title)
        print("Chat type:", chat.type)
        print("Chat ID:", chat.id)

    # optional: confirm in-group
    if update.effective_message:
        await update.effective_message.reply_text(f"Detected chat ID: {chat.id}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await any_update(update, context)

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.ALL, any_update))

if __name__ == "__main__":
    app.run_polling()
