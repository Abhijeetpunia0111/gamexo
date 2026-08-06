# gamexo-pos

A standalone walk-in counter POS, hosted and versioned independently from the admin dashboard — but talking to the **same backend/database**. React + Tailwind, same conventions as the dashboard it was split from.

## Flow

Home screen offers two entry points:

- **Walk-in Booking** — sport → court → date/time (auto-picked to the soonest real-available slot, editable) → player details (name + phone required, email/customer ID optional) → add-ons → payment (choose a method, then **Pay now** or **Check in, pay later**) → invoice/ticket with WhatsApp, SMS, email, print, PDF and native-share options.
- **Add-ons** — browse kit, then either attach it to a court already in play (a real `PATCH /bookings/{id}`) or ring up a counter sale (a local receipt — the backend has no anonymous-sale endpoint yet).

## Wired to the real API

This app calls the backend directly for sports, courts, real per-slot availability (`/courts/availability`), equipment inventory, booking creation, payments and invoicing. Point it at your deployment via `.env` (copy from `.env.example`):

```
VITE_API_BASE_URL=https://your-api-host
VITE_TENANT_SLUG=your-academy-slug
```

## Dev

```bash
npm install    # or pnpm install
npm run dev    # http://localhost:5174
```

Runs on port 5174 by default. If the backend restricts CORS by origin, add this app's dev/prod origin(s) to its allowlist.

## Build

```bash
npm run build      # tsc -b && vite build -> dist/
npm run typecheck
npm run lint
```

## Regenerating API types

`src/api/schema.d.ts` / `src/api/openapi.json` are generated from the backend's OpenAPI schema. Re-run against a live backend:

```bash
VITE_API_BASE_URL=http://localhost:8000 npm run generate:api
```
