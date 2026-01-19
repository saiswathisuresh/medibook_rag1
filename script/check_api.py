import os
import requests
from dotenv import load_dotenv

# ---------------- LOAD ENV ----------------
load_dotenv()

GROK_API_KEY = os.getenv("GROK_API_KEY")
GROK_API_URL = os.getenv("GROK_API_URL")  # Example: https://api.x.ai

if not GROK_API_KEY or not GROK_API_URL:
    print("❌ Please set GROK_API_KEY and GROK_API_URL in your .env file.")
    exit(1)

# ---------------- TEST API ----------------
url = f"{GROK_API_URL}/v1/models"

headers = {
    "Authorization": f"Bearer {GROK_API_KEY}"
}

try:
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code == 200:
        models = response.json()
        print("✅ Grok API is reachable!")
        print("Available models:")
        for m in models.get("data", []):
            print(f" - {m.get('name')}")
    elif response.status_code == 401:
        print("❌ Authentication failed! Check your GROK_API_KEY.")
    else:
        print(f"❌ API returned status code {response.status_code}")
        print(response.text)
except requests.exceptions.RequestException as e:
    print(f"❌ Failed to connect to Grok API: {e}")
