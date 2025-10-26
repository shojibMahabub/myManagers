import ollama
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv('TELEGRAM_MANAGER_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_MANAGER_BOT_CHAT_ID')

def send_request_to_ai(user_text):
    model_name = 'gemma3:4b'

    chat_history = [
        {
            'role': 'system',
            'content': 'Your are a friend of the role user. You like to travel, '
                       'you visited many countries'
                       'You are very experienced and talented Astronaut, Software Engineer, Entrepreneur.'
                       'You not only like to talk about work but also life.'
                       'reply in random message length, dont send same length message every time'
                       'reply text of the user in humanly nature, be humble, funny, act like a close friend.'
        },
        {
            'role': 'user',
            'content': user_text
        }
    ]

    # Send the chat request to Ollama
    try:
        response = ollama.chat(model=model_name, messages=chat_history)
        chat_history.append({'role': 'assistant', 'content': response['message']['content']})
        return response['message']['content']

    except Exception as e:
        return f"An error occurred: {e}"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    try:
        ai_reply = send_request_to_ai(user_text)
    except Exception as e:
        ai_reply = f"⚠️ Error contacting Ollama: {e}"

    await update.message.reply_text(f"{ai_reply}")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()