import os
import requests
import json
from fastapi import FastAPI, Query, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Vyapar AI - Smart Sales Intelligence Agent", version="2.0.0")

# 🌐 नेपाल र विश्वभरिका ई-कमर्स वेबसाइटमा जोड्न मिल्ने गरी सुरक्षा खुल्ला गरिएको
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔐 रेन्डर ड्यासबोर्डबाट सुरक्षित साँचोहरू तान्ने (ब्रह्मास्त्र)
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "VYAPAR_AI_MESSENGER_SECRET_TOKEN_2083")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# 🏢 सेल्सम्यानको महा-बौद्धिक नियम (System Instruction)
HONS_SYSTEM_PROMPT = (
    "You are a highly intelligent, persuasive, and empathetic AI Sales Executive working for Himalayan Online Service (HONS), "
    "a top-tier Internet Service Provider (ISP) in Nepal. Your primary goal is to convert inquiries into paying customers.\n\n"
    "CRITICAL BUSINESS KNOWLEDGE:\n"
    "1. Service Locations: Kathmandu, Bhaktapur, Lalitpur, Hetauda, and Kolhabi Municipality in Bara.\n"
    "2. Kolhabi Advantage: We have an exclusive local branch with a dedicated team of fiber technicians stationed permanently in Kolhabi for lightning-fast support.\n"
    "3. New Year 2083 Mega Campaign: We are offering 100Mbps superfast fiber internet combined with an advanced dual-band 5G Router. "
    "If they pay for 12 months, they get 1 month completely BONUS (13 months total)! Highlight that this is perfect for lag-free 4K video streaming and connecting multiple devices smoothly.\n"
    "4. Pricing & Objection Handling: Our price is already the best-value in Nepal considering the premium 5G router and bonus month. If a customer bargains, says 'ali discount dinus na' or asks for cheaper rates, politely explain that the current package saves them the most money annually. Frame it as an investment rather than an expense.\n"
    "5. Technical Complaints: If a user complains 'net chalena' or 'net slow chha', do not argue. Immediately ask for their Customer ID or Registered Phone Number, and confidently assure them that the HONS expert fiber support team is checking their line right now.\n\n"
    "RESPONSE RULES:\n"
    "- Match the customer's language preference. If they write in Roman Nepali (e.g., 'price kati ho?'), reply in natural, engaging Roman Nepali. If they write in pure Nepali, reply in beautiful, professional Nepali. If English, reply in English.\n"
    "- Never act like a rigid bot. Be warm, use polite expressions, keep sentences punchy, and always end with an inviting call-to-action (e.g., 'Hajur ko shuva naam ke hola?', 'Jod्नका लागि ठेगाना कहाँ पर्छ होला साहुजी?')."
)

def get_smart_ai_response(user_message: str) -> str:
    """गुगल जेमिनी इन्जिनबाट बुलेट स्पीडमा बुद्धिमानी सेल्स रिप्लाई निकाल्ने फंक्सन"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}
        
        # 🎯 शत-प्रतिशत ग्यारेन्टी चल्ने आधिकारिक गुगल जेमिनी पेलोड फम्र्याट
        payload = {
            "contents": [{
                "role": "user",
                "parts": [{
                    "text": f"Context & Instructions:\n{HONS_SYSTEM_PROMPT}\n\nCustomer's Message: '{user_message}'\n\nWrite a highly professional, contextual sales response following all matching language guidelines:"
                }]
            }],
            "generationConfig": {
                "temperature": 0.6,
                "topP": 0.9,
                "maxOutputTokens": 300
            }
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        res_json = response.json()
        
        # 🔍 ब्याकइन्डमा डेटा पक्का गर्ने स्मार्ट सुरक्षा कडी
        if 'candidates' in res_json and len(res_json['candidates']) > 0:
            parts = res_json['candidates'][0]['content']['parts']
            if len(parts) > 0:
                return parts[0]['text'].strip()
        
        # यदि कुनै कारणवश एपीआई ब्लक भयो भने सुरक्षित लग प्रिन्ट गर्ने
        print(f"⚠️ Unexpected Gemini API Structure: {json.dumps(res_json)}")
        return "नमस्कार! हजुरको म्यासेज प्राप्त भयो। हाम्रो HONS हेल्पडेस्क टिमले हजुरलाई तुरुन्तै सम्पर्क गर्नेछ। हजुरको फोन नम्बर पाउन सकिन्छ?"
        
    except requests.exceptions.Timeout:
        print("❌ Gemini API Timeout encountered.")
        return "नमस्कार! हजुरको म्यासेज सिस्टममा दर्ता भएको छ। हाम्रो प्रतिनिधिले हजुरलाई केही मिनेटमै म्यासेज गर्नुहुनेछ।"
    except Exception as e:
        print(f"❌ Smart Agent System Error: {e}")
        return "नमस्कार! हजुरको सोधपुछको लागि धन्यवाद। हाम्रो आधिकारिक सेल्स प्रतिनिधिले हजुरलाई तुरुन्तै रिप्लाई गर्नुहुनेछ।"

@app.get("/")
def home():
    """सर्भर जागै छ कि छैन भनेर चेक गर्ने अनलाइन ढोका"""
    return {
        "status": "Success",
        "message": "Smart AI Sales Intelligence Agent is fully operational on Render Cloud!",
        "engine": "Google Gemini 1.5 Flash (Production Ready)"
    }

@app.get("/api/v1/webhook/facebook")
def facebook_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: int = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """फेसबुक डेभलपरलाई प्रमाणीकरण गर्ने गेटवे"""
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return Response(content=str(hub_challenge), media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification token mismatch")

@app.post("/api/v1/webhook/facebook")
async def facebook_message(request: Request):
    """फेसबुक मेसेन्जरबाट आउने ग्राहकको म्यासेज ह्यान्डल गर्ने मुख्य इन्जिन"""
    data = await request.json()
    try:
        if data.get("object") == "page":
            for entry in data.get("entry", []):
                for messaging_event in entry.get("messaging", []):
                    # केवल टेक्स्ट म्यासेज आएको छ भने मात्र रिप्लाई दिने (इको वा डेलिभरी रिपोर्ट ब्लक गर्ने)
                    if messaging_event.get("message") and "text" in messaging_event["message"]:
                        sender_id = messaging_event["sender"]["id"]
                        incoming_message = messaging_event["message"]["text"]
                        
                        print(f"🔹 Incoming Message from Customer [{sender_id}]: '{incoming_message}'")
                        
                        # स्मार्ट एआईबाट जवाफ निकाल्ने
                        reply_text = get_smart_ai_response(incoming_message)
                        
                        # फेसबुक ग्राफ एपीआई मार्फत म्यासेज पठाउने
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
