Vyapar AI Employee - OpenAI Production Build

This build migrates the project from Gemini-first to OpenAI-first and adds:





FastAPI web service



Telegram webhook mode for production



Telegram polling mode for local testing



OpenAI Responses API primary provider



Optional Gemini fallback



SQLAlchemy memory database



SQLite local development support



Postgres production-ready support through DATABASE_URL



Deterministic memory answers for name/city/phone/company recall



Better memory extraction that does not save questions like Mero naam ke ho? as facts



Knowledge base and product catalog injection



Tenant-aware company profile loading from company_profiles.json via COMPANY_ID



Rate limiting and webhook secret validation

Render Environment Variables

Minimum:

TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_MODE=webhook
APP_BASE_URL=https://your-render-service.onrender.com
TELEGRAM_WEBHOOK_SECRET=make_a_long_random_secret
COMPANY_ID=hons
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-5.4-mini
OPENAI_STORE=false
DATABASE_URL=sqlite:///./data/vyapar.db

Each deployment uses one COMPANY_ID that must exist in company_profiles.json.
Add a new tenant by adding a new key to that file and deploying with the matching COMPANY_ID.

Recommended for real production:

DATABASE_URL=your_render_postgres_external_or_internal_url

Render Settings

Build command:

pip install -r requirements.txt

Start command:

python main.py

Health check path:

/healthz

Telegram Test Messages

Send these after deployment:

Mero naam Khemraj Adhikari ho
Ma Kathmandu baschhu
Mero naam ke ho?
Ma kaha baschhu?
Ma ISP business chalauchhu
Internet slow chha, ke garne?

Expected logs:

APP_STARTUP
COMPANY_PROFILE_LOADED
TELEGRAM_WEBHOOK_SET
TELEGRAM_UPDATE_RECEIVED
MEMORY_FACTS_EXTRACTED
DIRECT_MEMORY_ANSWER
OPENAI_RESPONSE_OK
TELEGRAM_REPLY_SENT

Important Notes





For local testing, set TELEGRAM_MODE=polling.



For production Render deployment, use TELEGRAM_MODE=webhook.



If you keep SQLite on Render without persistent disk, memory can be lost on redeploy. Use Render Postgres for real production memory.



Do not commit real API keys to GitHub.
