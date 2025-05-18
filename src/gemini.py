import requests
from dotenv import load_dotenv
from config import ConfigManager

load_dotenv()

def gemini(prompt):
    config = ConfigManager()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={config.get_gemini_key()}"
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]

    else:
        print(f"Error: {response.status_code}")
        return None

print(gemini("hi"))
