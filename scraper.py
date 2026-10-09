import os
import requests
from bs4 import BeautifulSoup
import json

# --- 1. TARGET BATTLEFIELD 6 SOURCES ---
TARGET_URLS = [
    "https://www.ea.com/games/battlefield/news",  # Official Battlefield News Hub
    "https://twitter.com/Battlefield"            # Official Battlefield X Account
]

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
WORKER_URL = os.environ.get("WORKER_URL")        # Your Cloudflare Worker endpoint URL
WORKER_SECRET = os.environ.get("WORKER_SECRET")  # Your secret token for security

def fetch_web_content():
    """Fetches text content specifically from Battlefield 6 target websites."""
    combined_text = ""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    for url in TARGET_URLS:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                # Extract paragraph, heading, and tweet/article elements
                elements = soup.find_all(['p', 'h1', 'h2', 'h3', 'article', 'span'])
                page_text = " ".join([el.get_text() for el in elements])
                combined_text += f"\n--- Source: {url} ---\n" + page_text[:4000]
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
            
    return combined_text

def analyze_with_deepseek(text):
    """Sends the Battlefield text to DeepSeek to extract event JSON parameters."""
    if not DEEPSEEK_API_KEY or not text:
        print("Missing DeepSeek API key or text content.")
        return None
    
    prompt = f"""
    Analyze the following official Battlefield 6 news and social updates. Determine if there is an active or upcoming in-game event (like Double XP, triple XP, new season, community mission, or tactical update).
    Return ONLY a valid JSON object with these exact keys:
    - "event_active": true or false
    - "event_type": string (name of the event, e.g., "Double XP Weekend", or null if none)
    - "start_date": string in YYYY-MM-DD format (or null)
    - "end_date": string in YYYY-MM-DD format (or null)
    - "multiplier": float number (e.g., 2.0, or 1.0 if normal)

    Text to analyze:
    {text}
    """

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"}
    }

    try:
        response = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=payload, timeout=30)
        result = response.json()
        content = result['choices'][0]['message']['content']
        return json.loads(content)
    except Exception as e:
        print(f"DeepSeek API error: {e}")
        return None

def push_to_worker(event_data):
    """Pushes the parsed event JSON to your Cloudflare D1 database worker."""
    if not WORKER_URL or not event_data:
        print("Missing Worker URL or event data.")
        return
        
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {WORKER_SECRET}"
    }
    
    try:
        res = requests.post(WORKER_URL, headers=headers, json=event_data, timeout=15)
        print("Worker sync response:", res.status_code, res.text)
    except Exception as e:
        print(f"Failed to push to worker: {e}")

if __name__ == "__main__":
    print("Step 1: Fetching Battlefield 6 source contents...")
    raw_text = fetch_web_content()
    
    print("Step 2: Processing text with DeepSeek AI...")
    event_json = analyze_with_deepseek(raw_text)
    
    if event_json:
        print("Extracted Event Data:", event_json)
        print("Step 3: Pushing results to Cloudflare Worker...")
        push_to_worker(event_json)
    else:
        print("No valid event data generated.")
