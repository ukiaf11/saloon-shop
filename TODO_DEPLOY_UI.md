# Task list — Railway deploy, images, claymorphism redesign, Phase 5

Order: deploy first so every later push reaches production automatically,
then the redesign, then Phase 5.

## A. Railway deployment
- [ ] Confirm the token can create a project (workspace vs project scope)
- [ ] Create a fresh project
- [ ] Provision Postgres and Redis
- [ ] Backend service (Django + gunicorn), healthcheck on `/healthz`
- [ ] Worker service (Celery) and Beat service (Celery Beat) from the same image
- [ ] Frontend service (Next.js standalone)
- [ ] Production env: `DJANGO_SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, `DATABASE_URL`,
      `REDIS_URL`, `ALLOWED_HOSTS`, CORS / CSRF origins — generated, never committed
- [ ] Fix what a real platform exposes:
  - [ ] gunicorn must bind `$PORT`, not a hard-coded 8000
  - [ ] `/healthz` must be exempt from the HTTPS redirect, or the platform
        healthcheck gets a 301 and marks the deploy failed
  - [ ] `NEXT_PUBLIC_*` values are baked at build time — pass them as build args
  - [ ] Media needs a persistent volume; a container's disk is wiped on redeploy
- [ ] Migrations run before each deploy, not by hand
- [ ] Seed salon, catalog, content and campaign config on the live database
- [ ] Verify: health, readiness, every public endpoint, the page, CORS
- [ ] CD: GitHub Action deploys to Railway on push to `main`

## B. Images
- [ ] Clay-style SVG illustrations for each service — original work, no licensing
      question, crisp at any size, and they match the clay aesthetic
- [ ] Real salon photography for the gallery from a permissively licensed source,
      credited in `CREDITS.md`
- [ ] Hero composition
- [ ] Gallery images seeded into backend media so the owner can replace them later

## C. Claymorphism redesign
- [ ] Design tokens: warm clay palette, soft dual inner shadows + outer drop,
      generous radii, pressed state for buttons
- [ ] Typography: soft rounded serif for display, rounded sans for body
- [ ] Rebuild every section: navbar, hero, campaign card, services, how it
      works, gallery, testimonials, why us, hours, location, FAQ, footer
- [ ] Rebuild the cart bar, discount reveal and checkout drawer
- [ ] Keep WCAG AA contrast — clay palettes are prone to low contrast
- [ ] Keep `prefers-reduced-motion`, keyboard focus and the 360px layout
- [ ] Verify in a real browser at 390px and 1280px, screenshot both

## D. Phase 5 — payments (partial until Razorpay keys exist)
- [ ] Provider abstraction + a fake provider for tests
- [ ] `Payment`, `PaymentWebhookEvent`, `PaymentGatewayConfig` (secret *references* only)
- [ ] Reserve a campaign slot at payment-create time and link `Order.daily_campaign`
- [ ] Webhook idempotency via `UNIQUE (provider, gateway_event_id)`
- [ ] **Blocked:** real Razorpay create/verify/webhook signature against the sandbox

## E. Close-out
- [ ] Update README, memory.md, IMPLEMENTATION_PLAN.md
- [ ] Commit, push, confirm CI + deploy green


---

## Status (2026-09-21)

- **A. Railway** — everything done and verified against the real production
  images **except provisioning**, which Railway refuses on the current plan.
  One command once credits exist (see memory.md §13).
- **B. Images** — done: original clay illustrations + 3 CC BY photos, credited.
- **C. Claymorphism** — done, AA contrast measured, mobile audited at 4 widths.
- **D. Phase 5** — not started this session; still needs Razorpay test keys.
- Added mid-task: **mobile responsiveness** (user request) — done and measured.
