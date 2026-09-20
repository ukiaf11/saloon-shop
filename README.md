# Salon Lucky Customer Platform

Mobile-first salon website with a daily lucky-slot campaign, online payment, QR
coupons and a role-based admin panel.

**Status:** Phases 1–2 complete (foundation, catalog & content). See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

| Document | Contents |
|---|---|
| [memory.md](memory.md) | Project state, invariants, open questions — **read this first** |
| [REQUIREMENTS.md](REQUIREMENTS.md) | DB / backend / UI / infra requirements, locked decisions |
| [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | Phased build plan with exit gates |
| `01_`–`03_*.md` | Original specifications (authoritative on any disagreement) |

## Stack

- **Frontend:** Next.js 16 (App Router), TypeScript, Tailwind 4, Motion, Zod
- **Backend:** Django 5 + DRF, managed with [uv](https://docs.astral.sh/uv/)
- **Data:** PostgreSQL 16, Redis 7, Celery + Beat
- **Payments:** Razorpay behind a provider-agnostic gateway interface

## Quick start

### With Docker (everything)

```bash
cp .env.example .env                      # host port overrides, if needed
cp backend/.env.example backend/.env      # fill DJANGO_SECRET_KEY
cp frontend/.env.example frontend/.env.local
docker compose up
```

Frontend on http://localhost:3000, API on http://localhost:8000.

> If a Postgres is already running on 5432, set `POSTGRES_HOST_PORT=5433` in the
> root `.env` and point `DATABASE_URL` at it.

### Backend only

```bash
cd backend
uv sync                                   # creates .venv from uv.lock
uv run python manage.py migrate
SEED_OWNER_PASSWORD='<12+ chars>' uv run python manage.py seed_salon
uv run python manage.py seed_catalog
uv run python manage.py seed_content
uv run python manage.py runserver
```

### Frontend only

```bash
cd frontend
npm ci
npm run dev
```

## Checks

```bash
# backend
cd backend
uv run ruff check . && uv run ruff format --check .
uv run python manage.py makemigrations --check --dry-run
uv run pytest -q

# frontend
cd frontend
npm run lint && npm run typecheck && npm run format:check && npm run test
```

CI runs all of the above plus a secret scan, dependency audits and Docker image
builds.

## Endpoints

| Path | Purpose |
|---|---|
| `GET /healthz` | Liveness — no dependencies, for the load balancer |
| `GET /api/v1/readiness` | Readiness — checks Postgres and Redis |
| `GET /api/v1/salon` | Salon profile, 7-day business hours, CMS content |
| `GET /api/v1/services` | Active services + categories |
| `GET /api/v1/gallery` | Gallery images |
| `GET /api/v1/testimonials` | Published testimonials |
| `GET /api/v1/faqs` | Published FAQs |
| `GET /api/v1/legal/{slug}` | Latest published legal page (terms / privacy / refunds / promotion-rules) |

Response shapes are fixed by [API_CONTRACT_PHASE2.md](API_CONTRACT_PHASE2.md); the
backend serializers and the frontend Zod schemas both answer to it.

## Things to know before changing code

These are load-bearing. The full list is in [memory.md](memory.md) §5.

1. **Money is integer paise.** No floats in the money path, anywhere. Use
   `common.money` on the backend and `src/lib/money.ts` for display only.
2. **The browser sends `service_ids` and contact fields only.** The backend
   computes every price, discount and total; payment amounts are read from
   `Order.total_paise`, never from a request body.
3. **Idempotency comes from database unique constraints**, not application-level
   existence checks. The payment-verify and webhook paths race by design.
4. **Winning positions never leave the server** — not in an API response, a
   serializer, a log line or an error message. `common.masking` redacts them.
5. **Capacity admission happens under `SELECT ... FOR UPDATE`** on the
   `DailyCampaign` row. Use `common.locks`, which refuses to run outside a
   transaction.
6. **Never commit secrets.** `.env` is gitignored, pre-commit runs gitleaks, and
   CI scans history.
7. **Service prices change only through `catalog.services.change_service_price()`.**
   A direct `.save()` that alters `price_paise` raises — price history is an audit
   requirement, not a convenience.
8. **Public cache invalidation is explicit.** Adding a public endpoint means adding
   its key to `common/cache.py` and a signal that drops it. TTL is only a backstop.
