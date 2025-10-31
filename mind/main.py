import google.generativeai as genai
import os
import ollama

def connectGemini(user_text):
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(user_text)
    return response.text


def connectOllama(prompt):
    model_name = 'llama3.1:latest'

    try:
        response = ollama.chat(model=model_name, messages=prompt)
        return response['message']['content']

    except Exception as e:
        return f"An error occurred: {e}"