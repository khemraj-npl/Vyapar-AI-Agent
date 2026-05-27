import os
import requests
from fastapi import FastAPI, Query, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types

app = FastAPI(title="Vyapar AI - Smart Sales Intelligence Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔐 सुरक्षा कडीहरू
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "VYAPAR_AI_MESSENGER_SECRET_TOKEN_2083")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# 🤖 गुगलको आधिकारिक क्लायन्ट इन्जिन सुरु गरियो (यसले आफैँ यूआरएल मिलाउँछ)
client = genai.Client(api_key=GEMINI_API_KEY)

# 🏢 हन्स (HONS) को व्यापार प्रवर्द्धन गर्ने महा-बौद्धिक नियम
HONS_SYSTEM_PROMPT = (
    "You are a highly intelligent, persuasive, and empathetic AI Sales Executive working for Himalayan Online Service (HONS), "
    "a top-tier Internet Service Provider (ISP) in Nepal. Your primary goal is to convert inquiries into paying customers.\n\n"
    "CRITICAL BUSINESS KNOWLEDGE:\n"
    "1. Service Locations: Kathmandu, Bhaktapur, Lalitpur, Hetauda, and Kolhabi Municipality in Bara.\n"
    "2. Kolhabi Advantage: We have an exclusive local branch with a dedicated team of fiber technicians stationed permanently in Kolhabi for lightning-fast support.\n"
    "3. New Year 2083 Mega Campaign: We are offering 100Mbps superfast fiber internet combined with an advanced dual-band 5G Router. "
    "If they pay for 12 months, they get 1 month completely BONUS (13 months total)! Highlight that this is perfect for lag-free 4K video streaming and connecting multiple devices smoothly.\n"
    "4. Pricing & Objection Handling: Our price is already the best-value in Nepal. If a customer bargains, says 'ali discount dinus na' or asks for cheaper rates, politely explain that the current package saves them the most money annually.\n"
    "5. Technical Complaints: If a user complains 'net chalena' or 'net slow chha', ask for their Customer ID or Registered Phone Number, and confidently assure them that the HONS expert fiber support team is checking their line right now.\n\n"
    "RESPONSE RULES:\n"
    "- Match the customer's language preference. If they write in Roman Nepali (e.g., 'price kati ho?'), reply in natural, engaging Roman Nepali. If they write in pure Nepali, reply in beautiful, professional Nepali. If English, reply in English.\n"
    "- Keep sentences punchy and always end with an inviting call-to-action."
)

def get_smart_ai_response(user_message: str) -> str:
    """गुगलको आधिकारिक SDK प्रयोग गरेर बुलेट स्पीडमा बुद्धिमानी सेल्स रिप्लाई निकाल्ने फंक्सन"""
    try:
        # 🚀 आधिकारिक सुरक्षित तरिका (नो यूआरएल झन्झट)
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=HONS_SYSTEM_PROMPT,
                temperature=0.6,
                max_output_tokens=300
            )
        )
        if response.text:
            return response.text.strip()
        return "नमस्कार! हजुरको म्यासेज प्राप्त भयो। हाम्रो HONS टिमले हजुरलाई तुरुन्तै सम्पर्क गर्नेछ।"
    except Exception as e:
        print(f"❌ Official Gemini SDK Error: {e}")
        return "नमस्कार! हजुरको सोधपुछको लागि धन्यवाद। हाम्रो प्रतिनिधिले हजुरलाई तुरुन्तै रिप्लाई गर्नुहुनेछ।"

@app.get("/")
def home():
    return {"status": "Smart AI Sales Agent is running perfectly on Render Cloud!"}

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
                    if messaging_event.get("message") and "text" in messaging_event["message"]:
                        sender_id = messaging_event["sender"]["id"]
                        incoming_message = messaging_event["message"]["text"]
                        
                        print(f"🔹 Incoming Message from Customer: '{incoming_message}'")
                        reply_text = get_smart_ai_response(incoming_message)
                        
                        fb_url = f"https://graph.facebook.com/v20.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
                        payload = {
                            "recipient": {"id": str(sender_id)},
                            "message": {"text": reply_text},
                            "messaging_type": "RESPONSE"
                        }
                        fb_res = requests.post(fb_url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
                        print(f"🔸 Sales AI Response Sent. Facebook Status: {fb_res.status_code}")
    except Exception as e:
        print(f"❌ Error inside Facebook Webhook Core: {e}")
    return {"status": "EVENT_RECEIVED"}
