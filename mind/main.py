import google.generativeai as genai
import os
import ollama

def connectGemini(user_text):
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(user_text)
    return response.text


def connectOllama(user_text):
    model_name = 'gemma3:4b'

    chat_history = [
        {
            'role': 'system',
            'content': 'Your are a friend of the role user. Reply to the user in humanly nature.'
        },
        {
            'role': 'user',
            'content': user_text
        }
    ]

    try:
        response = ollama.chat(model=model_name, messages=chat_history)
        chat_history.append({'role': 'assistant', 'content': response['message']['content']})
        return response['message']['content']

    except Exception as e:
        return f"An error occurred: {e}"