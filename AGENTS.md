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

### Secrets / external services (non-obvious)
- `OPENAI_API_KEY` is required only for LLM-generated replies. Without it the server still
  starts and the deterministic paths (memory write/recall, greeting, escalation, language
  routing) work; LLM turns return a graceful "temporarily having trouble" fallback instead.
- `TELEGRAM_BOT_TOKEN` is required for actual Telegram polling/webhook traffic. Without it the
  server runs fine but logs `TELEGRAM_DISABLED` and cannot send/receive Telegram messages.
  You can exercise the core engine directly via `generate_employee_reply(user_id, text)`
  without any Telegram token.

### Business owner dashboard
- Server-rendered (Jinja2 + Tailwind CDN) multi-tenant dashboard mounted at `/dashboard`
  (`dashboard.py` + `templates/`). Pages: login, overview, products (CRUD), leads.
- Create/update an owner account: `python admin_create_owner.py <email> <password> <company_id>`.
  Owners only see data for their own `company_id`. Session is a signed cookie
  (`auth.py`); set `DASHBOARD_SECRET_KEY` in production.
- **Company profiles are now DB-backed** (`company_profile` table). On first load
  `company_profiles.json` seeds the DB once (`COMPANY_PROFILES_SEEDED`); after that the DB
  is the source of truth and the dashboard edits it. Editing `company_profiles.json` later
  will NOT override an existing DB row — delete that company's `company_profile` row to
  re-seed from the file. The AI engine reads profiles through `company_manager.get_company*()`,
  unchanged, so dashboard edits are immediately reflected in replies.

### Tests / lint
- The repo has no automated test suite and no configured linter/formatter.
