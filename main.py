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

# 🔐 सुरक्षा कडीहरू (रेन्डरबाट सिधै तानिन्छ)
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "VYAPAR_AI_MESSENGER_SECRET_TOKEN_2083")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# 🏢 हन्स (HONS) को व्यापार प्रवर्द्धन गर्ने महा-बौद्धिक नियमहरू
HONS_SYSTEM_PROMPT = (
    "You are a highly intelligent, friendly, and persuasive AI Sales Executive working for Himalayan Online Service (HONS), "
    "a premier Internet Service Provider (ISP) in Nepal. Your primary goal is to convert inquiries into paying customers.\n\n"
    "CRITICAL BUSINESS KNOWLEDGE:\n"
    "- Service Locations: Kathmandu, Bhaktapur, Lalitpur, Hetauda, and Kolhabi Municipality in Bara.\n"
    "- Kolhabi Advantage: We have an exclusive local branch with dedicated fiber technicians stationed permanently in Kolhabi for fast support.\n"
    "- New Year 2083 Campaign: 100Mbps superfast fiber internet + advanced dual-band 5G Router. Pay for 12 months, get 1 month completely BONUS (13 months total)! Perfect for lag-free 4K video streaming and multiple devices.\n"
    "- Discount Handling: Our price is already the best-value in Nepal with the free 5G router and bonus month. If a customer bargains or says 'ali discount dinus na', politely explain that the 12-month pack saves them the most money annually.\n"
    "- Technical Complaints: If a user complains 'net chalena', ask for their Customer ID or Registered Phone Number, and assure them our fiber team is checking it immediately.\n\n"
    "RESPONSE RULES:\n"
    "- Match the customer's language preference. If they write in Roman Nepali (e.g., 'price kati ho?'), reply in natural Roman Nepali. If they write in pure Nepali, reply in beautiful Nepali.\n"
    "- Keep answers concise, polite, and always end with an inviting question to close the sale."
)

def get_smart_ai_response(user_message: str) -> str:
    """सिधै गुगलको आधिकारिक र स्थायी v1 गेटवे हिट गर्ने सफा र ग्यारेन्टी फंक्सन"""
    try:
        # 🚀 यो गुगलको शत-प्रतिशत चल्ने आधिकारिक स्टेबल यूआरएल हो
        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}
        
        # 🎯 कोष्ठकहरू पूर्ण रूपमा भेरिफाई गरिएको पेलोड स्ट्रक्चर
        payload = {
            "contents": [{
                "parts": [{
                    "text": f"Context & Instructions:\n{HONS_SYSTEM_PROMPT}\n\nCustomer Message: '{user_message}'\n\nAI Executive Response:"
                }]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 300
            }
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        res_json = response.json()
        
        # 🔍 डेटा सुरक्षित तरिकाले तान्ने कडी
        if 'candidates' in res_json and len(res_json['candidates']) > 0:
            return res_json['candidates'][0]['content']['parts'][0]['text'].strip()
            
        print(f"⚠️ API Error Response: {res_json}")
        return "नमस्कार! हजुरको म्यासेज प्राप्त भयो। हाम्रो HONS हेल्पडेस्क टिमले हजुरलाई तुरुन्तै सम्पर्क गर्नेछ।"
        
    except Exception as e:
        print(f"❌ Gemini Core Error: {e}")
        return "नमस्कार! सोधपुछको लागि धन्यवाद। हाम्रो प्रतिनिधिले हजुरलाई तुरुन्तै रिप्लाई गर्नुहुनेछ।"

@app.get("/")
def home():
    return {"status": "Smart AI Sales Agent is Live on Verified Gemini v1 Engine!"}

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
                        
                        print(f"🔹 Received text from Facebook: '{incoming_message}'")
                        reply_text = get_smart_ai_response(incoming_message)
                        
                        fb_url = f"https://graph.facebook.com/v20.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
                        payload = {
                            "recipient": {"id": str(sender_id)},
                            "message": {"text": reply_text},
                            "messaging_type": "RESPONSE"
                        }
                        fb_res = requests.post(fb_url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
                        print(f"🔸 Response Sent to Facebook. Status: {fb_res.status_code}")
    except Exception as e:
        print(f"❌ Core Webhook Error: {e}")
    return {"status": "EVENT_RECEIVED"}
