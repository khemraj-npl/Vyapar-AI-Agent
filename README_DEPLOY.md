# Vyapar AI Employee - OpenAI Production Build

This build migrates the project from Gemini-first to OpenAI-first and adds:

- FastAPI web service
- Telegram webhook mode for production
- Telegram polling mode for local testing
- OpenAI Responses API primary provider
- Optional Gemini fallback
- SQLAlchemy memory database
- SQLite local development support
- Postgres production-ready support through `DATABASE_URL`
- Deterministic memory answers for name/city/phone/company recall
- Better memory extraction that does not save questions like `Mero naam ke ho?` as facts
- Knowledge base and product catalog injection
- Tenant-aware company profile loading from `company_profiles.json`
- **Multi-tenant channel credentials** in the `tenants` DB table (Telegram + Facebook Messenger per company)
- Smart lead qualification with stages, scoring, and sales-mode replies (Phase 2)
- Rate limiting and per-tenant webhook secret validation

## Multi-tenant channels (Telegram + Facebook)

Business rules and tenant metadata stay in `company_profiles.json`. **Product catalogs** live in the **`products`** DB table. **Channel secrets** (bot tokens, page IDs) live in the **`tenants`** table.

| Column | Purpose |
|--------|---------|
| `company_id` | FK to business profile key (e.g. `hons`) |
| `telegram_bot_token` | Per-tenant Telegram bot token |
| `telegram_bot_username` | Bot username (optional resolver for webhooks) |
| `telegram_webhook_secret` | Per-tenant `X-Telegram-Bot-Api-Secret-Token` |
| `fb_page_id` | Facebook Page ID |
| `fb_access_token` | Page access token for Graph API replies |

**Upsert a tenant:**

```bash
python admin_upsert_tenant.py --company-id hons \
  --telegram-bot-token YOUR_TOKEN \
  --telegram-bot-username your_bot \
  --telegram-webhook-secret random-secret \
  --fb-page-id YOUR_PAGE_ID \
  --fb-access-token YOUR_PAGE_TOKEN \
  --print
```

**One-time migration from env vars:**

```bash
python admin_upsert_tenant.py --bootstrap-env --print
```

On startup, `bootstrap_tenant_from_env()` also seeds the active `COMPANY_ID` from legacy env if set.

**Webhook URLs:**

| Channel | URL |
|---------|-----|
| Telegram (recommended) | `POST /telegram/webhook/{company_id}` |
| Telegram (by username) | `POST /telegram/webhook/by-username/{bot_username}` |
| Telegram (legacy single-tenant) | `POST /telegram/webhook` — resolves tenant by webhook secret |
| Facebook | `GET/POST /facebook/webhook` — resolves tenant by `page_id` in payload |

Facebook webhook verification uses global `FB_VERIFY_TOKEN`. Each page's access token is read from `tenants.fb_access_token`.

## Render Environment Variables

Minimum (multi-tenant):

```txt
TELEGRAM_MODE=webhook
APP_BASE_URL=https://your-render-service.onrender.com
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-5.4-mini
OPENAI_STORE=false
DATABASE_URL=your_render_postgres_url
FB_VERIFY_TOKEN=your_facebook_verify_token
```

Optional bootstrap (copied into `tenants` on startup):

```txt
COMPANY_ID=hons
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_BOT_USERNAME=your_bot
TELEGRAM_WEBHOOK_SECRET=make_a_long_random_secret
FB_PAGE_ID=your_page_id
FB_ACCESS_TOKEN=your_page_access_token
```

Each `company_id` must exist in `company_profiles.json`. Add tenants with `admin_upsert_tenant.py` — one row per company.

## Product catalog (DB-backed)

Products are stored exclusively in the **`products`** table. `company_profiles.json` must not contain a `products` array — manage catalogs via the dashboard API below.

| Column | Purpose |
|--------|---------|
| `id` | Primary key |
| `company_id` | Tenant FK |
| `name` | Product or service name |
| `description` | Details for search + matched replies |
| `price` | Integer amount in tenant currency |
| `stock_status` | `in_stock`, `out_of_stock`, `low_stock`, `pre_order`, `discontinued` |
| `category` | Grouping for dashboard + prompt summaries |

**Seed a tenant catalog (example — HONS ISP packages):**

```bash
curl -X POST "https://your-app.onrender.com/dashboard/hons/products" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_DASHBOARD_API_KEY" \
  -d '{"name":"100 Mbps Internet Package","price":10000,"stock_status":"in_stock","category":"Internet Packages","description":"100 Mbps package (13 months)"}'
```

Repeat for each product, or seed HONS defaults locally / on Render:

```bash
python admin_seed_hons_products.py --company-id hons --print
```

**Dashboard CRUD API** (set `DASHBOARD_API_KEY`; header optional in dev when unset):

| Method | Path |
|--------|------|
| GET | `/dashboard/{company_id}/products` |
| POST | `/dashboard/{company_id}/products` |
| GET | `/dashboard/{company_id}/products/{id}` |
| PUT | `/dashboard/{company_id}/products/{id}` |
| DELETE | `/dashboard/{company_id}/products/{id}` |

When a tenant has more than `CATALOG_FULL_LIST_LIMIT` (default 8) products, `compose_system_prompt()` receives a **summarized markdown catalog** instead of the full list.

Recommended for real production:

```txt
DATABASE_URL=your_render_postgres_external_or_internal_url
LEAD_ACTIVE_DAYS=30
ADMIN_ALERT_ENABLED=false
```

## Lead qualification (generic commerce)

Lead stages: `new` → `interested` → `qualified` → `hot`.

**Qualified** requires **phone OR WhatsApp** plus **delivery/service location OR requested item/service** — score alone is not enough.

Industry-specific details (e.g. ISP Mbps) are stored in `leads.custom_signals` JSON, not core columns.

Core lead columns: `requested_item_or_service`, `delivery_or_service_location`, `delivery_or_service_status`, `custom_signals`.

Existing Postgres deployments: run `docs/migrations/004_generic_leads.sql` once, or rely on `init_db()` auto-migration on startup.

Export leads:

```bash
python admin_export_leads.py
```

### Lead test messages

```txt
2 pcs shoes order garne, Lalitpur ma deliver garnu
Mero phone 9801234567 ho, Pokhara ma blue t-shirt size L order garne
WhatsApp ma contact garnus 9801234567
Support hours kati ho?
Baluwatar ma 100 mbps internet chahiyo
```

Expected logs for lead flow:

```txt
LEAD_SIGNALS_DETECTED
LEAD_UPSERTED
SALES_MODE_ACTIVE
ADMIN_ALERT_PLACEHOLDER
EMPLOYEE_REPLY_GENERATED
```

## Render Settings

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
python main.py
```

Health check path:

```txt
/healthz
```

## Telegram Test Messages

Send these after deployment:

```txt
Mero naam Khemraj Adhikari ho
Ma Kathmandu baschhu
Mero naam ke ho?
Ma kaha baschhu?
Ma ISP business chalauchhu
Internet slow chha, ke garne?
```

Expected logs:

```txt
APP_STARTUP
COMPANY_PROFILE_LOADED
TELEGRAM_WEBHOOK_SET
TELEGRAM_UPDATE_RECEIVED
MEMORY_FACTS_EXTRACTED
DIRECT_MEMORY_ANSWER
OPENAI_RESPONSE_OK
TELEGRAM_REPLY_SENT
```

## Important Notes

- For local testing, set `TELEGRAM_MODE=polling`.
- For production Render deployment, use `TELEGRAM_MODE=webhook`.
- If you keep SQLite on Render without persistent disk, memory can be lost on redeploy. Use Render Postgres for real production memory.
- Do not commit real API keys to GitHub.
