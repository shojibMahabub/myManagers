import asyncio
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, ContextTypes
import os

BOT_TOKEN = os.getenv('TELEGRAM_MANAGER_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_MANAGER_BOT_CHAT_ID')

# Callback for button presses
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "approve":
        await query.edit_message_text("✅ You approved this job!")
        # TODO: trigger AI proposal generation here
    elif query.data == "reject":
        await query.edit_message_text("❌ You rejected this job!")

# Function to send a job with buttons
async def send_job(app, chat_id, job_title, job_link):
    keyboard = [
        [
            InlineKeyboardButton("Approve ✅", callback_data="approve"),
            InlineKeyboardButton("Reject ❌", callback_data="reject"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await app.bot.send_message(
        chat_id=chat_id,
        text=f"New Upwork job found:\n{job_title}\n{job_link}",
        reply_markup=reply_markup
    )

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CallbackQueryHandler(button_handler))

    # Send a test job once the bot starts
    async def on_startup(app):
        await send_job(app, CHAT_ID, "AI Developer Needed", "https://www.upwork.com/job-link")

    app.post_init = on_startup

    # Run the bot (polling)
    app.run_polling()