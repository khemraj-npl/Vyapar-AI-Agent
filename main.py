import os
import requests
from fastapi import FastAPI, Query, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Vyapar AI - Smart Sales Intelligence Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔐 सुरक्षा र प्रमाणिकरण
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "VYAPAR_AI_MESSENGER_SECRET_TOKEN_2083")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")  # 🚀 अब सिधै गुगलको आधिकारिक की चल्छ

HONS_SYSTEM_PROMPT = """
You are a smart, friendly, and persuasive AI Sales Employee working for Himalayan Online Service (HONS), a premier Internet Service Provider in Nepal. 

CRITICAL INFORMATION:
1. Locations: Kathmandu, Bhaktapur, Lalitpur, Hetauda, and Kolhabi Municipality in Bara. We have dedicated fiber technicians in Kolhabi branch.
2. Current Campaign (New Year 2083 Offer): 100Mbps superfast internet + advanced 5G Router. Pay for 12 months, get 1 month completely BONUS! Great for 4K streaming and multi-device.
3. Pricing & Discount Strategy: The offer is already best-value in Nepal. If asked for more discount or "discount dinus na", politely explain that with the free 5G router and 1-month bonus, it's already a massive deal, but encourage them that a 12-month lock-in saves the most money.
4. Support: If they complain "net chalena", ask for Customer ID/Phone number and tell them our fiber team is checking it.

TONE: Friendly, professional, natural Nepali (or Roman Nepali based on customer text). Concise and direct.
"""

def get_smart_ai_response(user_message: str) -> str:
    try:
        # 🚀 गुगल जेमिनीको आधिकारिक फ्री र बुलेट स्पीड एपीआई यूआरएल
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [{
                    "text": f"{HONS_SYSTEM_PROMPT}\n\nCustomer: {user_message}\nAI Employee:"
                }]
            }]
        }
        response = requests.post(url, json=payload, headers=headers)
        res_json = response.json()
        return res_json['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        print(f"❌ Gemini API Error: {e}")
        return "नमस्कार! हजुरको म्यासेज प्राप्त भयो। हाम्रो HONS टिमले हजुरलाई तुरुन्तै सम्पर्क गर्नेछ।"

@app.get("/")
def home():
    return {"status": "Smart AI Sales Agent is Live on Google Gemini Engine!"}

@app.get("/api/v1/webhook/facebook")
def facebook_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: int = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return Response(content=str(hub_challenge), media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification token mismatch")

@app.post("/api/v1/webhook/facebook")
async def facebook_message(request: Request):
    data = await request.json()
    try:
        if data.get("object") == "page":
            for entry in data.get("entry", []):
                for messaging_event in entry.get("messaging", []):
                    if messaging_event.get("message"):
                        sender_id = messaging_event["sender"]["id"]
                        incoming_message = messaging_event["message"].get("text", "")
                        
                        print(f"🔹 Received text: '{incoming_message}' from {sender_id}")
                        reply_text = get_smart_ai_response(incoming_message)
                        
                        fb_url = f"https://graph.facebook.com/v20.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
                        payload = {
                            "recipient": {"id": str(sender_id)},
                            "message": {"text": reply_text},
                            "messaging_type": "RESPONSE"
                        }
                        requests.post(fb_url, json=payload, headers={"Content-Type": "application/json"})
                        print("🔸 Sales AI Response Sent successfully via Gemini.")
    except Exception as e:
        print(f"❌ Error handling sales message: {e}")
    return {"status": "EVENT_RECEIVED"}
