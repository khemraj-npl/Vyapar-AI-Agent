# AGENTS.md

## Cursor Cloud specific instructions

### What this is
Single Python service: **Vyapar AI Employee**, a multi-tenant FastAPI web app that runs a
Telegram customer-support/sales bot backed by the OpenAI Responses API. Entry point is
`main.py`; the AI reply logic lives in `ai_employee_engine.generate_employee_reply`.
See `README.md` / `README_DEPLOY.md` for the product overview and Render deploy settings.

### Environment / running
- Python deps are installed into a local virtualenv at `.venv` by the update script.
  Run anything with `.venv/bin/python ...`.
- The app does **not** auto-load a `.env` file — it reads variables straight from the process
  environment via `os.getenv`. You must `export` the vars (or prefix the command) before
  running. `.env.example` lists every supported variable.
- Local dev defaults: `DATABASE_URL=sqlite:///./data/vyapar.db` (auto-creates `data/`),
  `COMPANY_ID=hons` (must exist in `company_profiles.json`).
- Run the server: `export DATABASE_URL=sqlite:///./data/vyapar.db COMPANY_ID=hons TELEGRAM_MODE=webhook PORT=10000 && .venv/bin/python main.py`
  (serves on port 10000). For local Telegram testing set `TELEGRAM_MODE=polling`.
- Initialize the DB schema standalone with `.venv/bin/python admin_init_db.py` (the server
  also calls `init_db()` on startup).
- Health check: `GET /healthz`; service info: `GET /`.

### Channels (transport adapters)
The AI "brain" is `ai_employee_engine.generate_employee_reply(user_id, text, company_id)` and is
platform-agnostic. Each chat platform is a thin adapter in its own module that calls the engine:
- **Telegram**: lives in `main.py` (webhook `/telegram/webhook` + polling). Needs `TELEGRAM_BOT_TOKEN`.
- **Facebook Messenger**: lives in `facebook_messenger.py`, routes `GET/POST /facebook/webhook` in
  `main.py`. `GET` is the verify handshake (`hub.verify_token` must equal `FACEBOOK_VERIFY_TOKEN`);
  `POST` validates `X-Hub-Signature-256` against `FACEBOOK_APP_SECRET`, then replies via the Graph
  API. Messenger user ids are namespaced as `fb:<sender_id>` so memory doesn't collide across
  channels. The POST handler always returns 200 (errors are logged) so Facebook doesn't disable the
  webhook on transient failures.

### Secrets / external services (non-obvious)
- `OPENAI_API_KEY` is required only for LLM-generated replies. Without it the server still
  starts and the deterministic paths (memory write/recall, greeting, escalation, language
  routing) work; LLM turns return a graceful "temporarily having trouble" fallback instead.
- `TELEGRAM_BOT_TOKEN` is required for actual Telegram polling/webhook traffic. Without it the
  server runs fine but logs `TELEGRAM_DISABLED` and cannot send/receive Telegram messages.
  You can exercise the core engine directly via `generate_employee_reply(user_id, text)`
  without any Telegram token.
- Facebook Messenger needs `FACEBOOK_PAGE_ACCESS_TOKEN` (send), `FACEBOOK_VERIFY_TOKEN` (webhook
  verify), and `FACEBOOK_APP_SECRET` (signature check); optional `FACEBOOK_GRAPH_VERSION`
  (default `v21.0`). Without the page token the server runs but logs `FACEBOOK_MESSENGER_DISABLED`.
  Facebook must reach the webhook over public HTTPS, so live testing needs a public tunnel
  (e.g. cloudflared/ngrok) or a deployed URL, plus the page subscribed to the app's `messages` event.

### Tests / lint
- The repo has no automated test suite and no configured linter/formatter.
