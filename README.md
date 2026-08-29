# Baran

Baran is an API-first, multi-tenant restaurant management and conversational ordering platform. This repository currently contains the Phase 0 foundation: deployable services, architectural boundaries, environment configuration, health checks, baseline security, observability, and test/CI plumbing.

## Architecture at a glance

- `backend/`: Django + Django REST Framework modular monolith
- `frontend/`: React + TypeScript SPA
- `docs/architecture/`: domain map, tenancy decision, initial ERD, and API conventions
- PostgreSQL is the source of truth; Redis is reserved for cache, rate limits, and queues.
- Tenant isolation uses a shared database/shared schema with mandatory `organization_id` scoping. See the ADR before adding tenant-owned models.

## Run locally

The responsive restaurant management console is available at `/manage`: owner registration, organization setup, branches, employees and branch assignments, menus, products, tables and downloadable QR codes, campaigns, schedules, stock, recipes, and reservations. See [the management setup guide](docs/operations/management-panel.md) for the complete first-restaurant workflow and dependency update commands.

1. Copy `.env.example` to `.env`.
2. Run `docker compose up --build`.
3. Open the UI at http://localhost:5173 and the API health endpoint at http://localhost:8000/api/v1/health/.

Useful commands are available in the `Makefile`. Phase 1 now implements identity, organizations, branches, membership/RBAC, JWT authentication, guest identity, and tenant enforcement.

## Phase 1 API

- `POST /api/v1/auth/register/` and `POST /api/v1/auth/token/`
- `GET /api/v1/auth/me/`
- `GET|POST /api/v1/organizations/`
- `GET|POST /api/v1/organizations/members/`
- `GET|POST /api/v1/organizations/branches/`

Tenant-owned endpoints require `Authorization: Bearer <access-token>` and `X-Organization-ID: <uuid>`. The tenant header selects context but never grants access; an active membership is always checked server-side.

## Phase 2 API

- `/api/v1/tables/` manages branch tables and `POST /api/v1/tables/{id}/rotate_qr/` revokes/reissues QR access.
- `/api/v1/tables/resolve/{token}/` safely resolves an active public table.
- `/api/v1/menus/catalogs/`, `categories/`, `items/`, and `ingredients/` manage the catalog.
- `/api/v1/menus/option-groups/`, `options/`, and `add-ons/` manage customization.
- `/api/v1/menus/availability/` stores branch stock, availability, and price overrides.
- `/api/v1/menus/public/{qr-token}/` returns the effective, branch-aware public menu without login.

Raw QR tokens are returned only when created or rotated; only their SHA-256 hashes are persisted. Menu prices use integer minor units and public availability combines item state with branch overrides and stock.

## Phase 3 customer flow

1. Open `/?qr=<table-qr-token>`; the SPA exchanges the QR for a short-lived `X-Table-Session` token.
2. The session-scoped menu and cart APIs require no login and cannot access another session.
3. `POST /api/v1/customer/cart/items/` accepts item/customization IDs and quantity—never a trusted price.
4. `POST /api/v1/customer/orders/confirm/` requires `Idempotency-Key`, revalidates availability and current prices, and atomically snapshots the cart into an order.
5. An authenticated customer can attach the guest session with `POST /api/v1/customer/session/claim/`.

Customer endpoints live under `/api/v1/customer/`: `sessions/`, `session/`, `menu/`, `cart/`, `cart/items/`, and `orders/`.

## Phase 4 operations

The staff UI is available at `/staff`. After JWT login it discovers the user's organization membership and assigned branches, then polls the branch order queue every eight seconds.

- `GET /api/v1/staff/context/` returns the active role and branch scope.
- `GET /api/v1/staff/orders/` supports `branch`, comma-separated `status`, and `updated_after` filters.
- `PATCH /api/v1/staff/orders/{id}/` performs a role-checked state transition and requires the current `version`.
- Every accepted transition creates an immutable `OrderStatusEvent` and transactional `NotificationOutbox` record.

Lifecycle: `pending → confirmed → preparing → ready → completed`, with controlled cancellation from non-final states. Cashiers accept/complete, kitchen roles prepare/ready, waiters complete ready orders, and managers can operate the full flow.

## Phase 5 menu assistant

The customer menu includes a session-scoped chat panel backed by the OpenAI Responses API when `OPENAI_API_KEY` is configured. The default model is `gpt-5.6-luna` and can be changed with `OPENAI_MODEL`; `AI_PROVIDER=local` forces the deterministic fallback.

The model starts with four read-only tools: `search_menu`, `get_food_details`, `recommend_menu`, and `get_restaurant_info`. Tool execution receives tenant/branch/table context from the authenticated table session, never from model-generated identifiers. Prices, availability, allergens, ingredients and restaurant facts always originate from database queries.

- `GET /api/v1/customer/chat/` returns the current session's conversation.
- `POST /api/v1/customer/chat/messages/` stores a customer message and returns the assistant response.
- Tool traces are retained for audit but are not exposed through the customer history endpoint.
- `python manage.py purge_expired_conversations` enforces conversation retention expiry.

## Phase 6 conversational ordering

The assistant can read, add, update, and remove cart lines through server-side tools. Every mutation is scoped to the current table session, recalculates trusted prices, validates availability and required options, and invalidates any older checkout preview.

- `prepare_checkout` creates a ten-minute `OrderConfirmation` preview; it does not create an order.
- The model has no order-creation tool. Final submission only happens through `POST /api/v1/customer/chat/confirmations/{id}/confirm/` or an exact affirmative customer reply while that preview is active.
- Confirmation verifies the session, expiry, active cart, and a SHA-256 cart fingerprint before atomically creating the order.
- The chat UI renders the authoritative cart total and a separate **تأیید و ثبت سفارش** button.
- OpenAI requests disable response storage and attach a stable pseudonymous `safety_identifier` derived from the table/customer session.

## Guardrails

- Never accept an organization identifier from a request body as proof of tenant access.
- Resolve tenant context from authenticated membership (staff) or a signed/opaque table session (guest).
- Application services own use-case orchestration; models must not call external services.
- AI is an adapter over trusted application tools and never a source of menu, price, or availability data.

## Phase 7 payments and invoices

Payment is a separate lifecycle from food preparation. Every attempt snapshots `Order.total` and currency on the server; client-supplied amounts are ignored. Supported methods are cash, card terminal, and online payment through a provider adapter.

- `POST /api/v1/customer/payments/` creates an idempotent payment attempt for the current table session.
- The bundled `mock_gateway` verifies the complete online flow locally; replace its adapter with a PSP without changing order logic.
- `GET /api/v1/customer/orders/{id}/invoice/` exposes a paid order's immutable invoice to its session only.
- `POST /api/v1/staff/orders/{id}/collect-payment/` lets cashiers and managers record cash/POS collection inside their branch scope.
- Successful payment writes an audit event, issues one invoice, cancels other pending attempts, and adds a transactional `payment.paid` outbox event.

## Phase 8 customer intelligence

Customers may create an optional account and claim the current table session. Personal endpoints require both the customer's JWT and that claimed session; QR/session possession alone never exposes profile or order history.

- `GET|PATCH /api/v1/customer/account/profile/` manages dietary preferences and separate AI, retention, and marketing consent flags.
- `GET /api/v1/customer/account/orders/` returns organization-scoped history; `POST .../{id}/reorder/` rebuilds the cart using current prices, availability, and customization validation.
- `/api/v1/customer/account/favorites/` manages real menu-item favorites inside the current organization.
- `GET /api/v1/customer/account/loyalty/` exposes an append-only point ledger. Paid claimed orders earn points exactly once.
- `POST /api/v1/customer/account/privacy/erase/` requires an explicit confirmation phrase and clears personalization, favorites, and consent while retaining legally relevant order/invoice records.
- The AI `get_customer_context` tool returns no personal context unless the signed-in customer has explicitly enabled AI personalization.

## Phase 9 advanced restaurant operations

- Campaigns support tenant-unique codes, branch scope, fixed/percentage discounts, date windows, minimum order, caps, and usage limits. Discounts are calculated server-side inside checkout.
- Orders support dine-in, takeaway, and delivery fulfillment; delivery requires an address.
- Menu schedules restrict menus by branch, weekday, and time window.
- Ingredient stock, recipe consumption, immutable stock movements, low-stock thresholds, and atomic order-time deduction are available under `/api/v1/operations/stock/` and `recipes/`.
- Customers can request a capacity-checked reservation; authorized restaurant staff manage its lifecycle through `/api/v1/operations/reservations/`.
- `GET /api/v1/staff/analytics/` returns scoped daily revenue, order count, average order value, popular products, reservations, and low-stock alerts.

## Phase 10 production and scale

- Redis backs caching, scoped API throttles, lightweight HTTP metrics, Celery brokerage, and task results.
- Celery workers dispatch transactional Outbox events with row locking and retry/backoff; Beat schedules dispatch and retention cleanup.
- `/health/` is process liveness, `/ready/` verifies PostgreSQL and Redis, and token-protected `/metrics/` emits Prometheus text metrics. Every response includes `X-Request-ID`, also present in structured JSON logs.
- Production uses Gunicorn and an unprivileged Nginx image with security headers. `compose.production.yaml` removes source mounts and separates API, worker, and the single scheduler.
- Sensitive endpoints have dedicated chat, checkout, payment, and reservation rate limits. Production settings fail fast on weak secrets and enable TLS redirect, HSTS preload, secure cookies, trusted origins, and database health checks.
- CI verifies formatting, migrations, Django deployment checks, backend/frontend tests, both Compose configurations, production image builds, and high/critical image vulnerabilities.
- `load-tests/smoke.js`, database backup/restore scripts, and `docs/operations/production-runbook.md` cover capacity checks, recovery drills, alerts, rotation, scaling, and rollback.
