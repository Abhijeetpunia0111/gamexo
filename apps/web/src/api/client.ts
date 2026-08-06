/**
 * Typed fetch wrapper over the gamexo API.
 *
 * No runtime dependency by design — paths and payloads are typed from the
 * generated `schema.d.ts`, so a backend change that breaks a call site shows up
 * at `tsc` time rather than in the browser.
 *
 * Two things every request needs and none of the call sites should have to
 * remember: the bearer token, and the tenant. Both are attached here.
 */
import type { paths } from './schema'
import { getTokens, setTokens, clearTokens } from './auth'

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '')
const TENANT = import.meta.env.VITE_TENANT_SLUG ?? 'xcourt'

/** The shared error envelope from the API — see app/core/errors.py::_envelope. */
type ErrorEnvelope = {
  error: { code: string; message: string; details?: Record<string, unknown> }
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown>

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }

  get isUnauthenticated() {
    return this.status === 401
  }
  get isForbidden() {
    return this.status === 403
  }
  get isNotFound() {
    return this.status === 404
  }
  get isConflict() {
    return this.status === 409
  }
}

async function toApiError(res: Response): Promise<ApiError> {
  let code = 'http_error'
  let message = `${res.status} ${res.statusText}`
  let details: Record<string, unknown> = {}
  try {
    const body = (await res.json()) as Partial<ErrorEnvelope>
    if (body?.error) {
      code = body.error.code ?? code
      message = body.error.message ?? message
      details = body.error.details ?? {}
    }
  } catch {
    /* non-JSON body (a proxy error page, say) — keep the status-line message */
  }
  return new ApiError(res.status, code, message, details)
}

type Query = Record<string, string | number | boolean | undefined | null>

function withQuery(path: string, query?: Query) {
  if (!query) return path
  const params = new URLSearchParams()
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== null) params.set(k, String(v))
  }
  const qs = params.toString()
  return qs ? `${path}?${qs}` : path
}

/**
 * A single in-flight refresh, shared by every 401 that lands while it runs.
 * Without this, a screen firing five queries at once on an expired token would
 * start five refreshes and four of them would race to store a stale pair.
 */
let refreshing: Promise<boolean> | null = null

async function refreshOnce(): Promise<boolean> {
  const tokens = getTokens()
  if (!tokens?.refresh_token) return false

  refreshing ??= (async () => {
    try {
      const res = await fetch(`${BASE_URL}/api/v1/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Tenant-ID': TENANT },
        body: JSON.stringify({ refresh_token: tokens.refresh_token }),
      })
      if (!res.ok) {
        clearTokens()
        return false
      }
      setTokens(await res.json())
      return true
    } catch {
      return false
    } finally {
      refreshing = null
    }
  })()

  return refreshing
}

type RequestOptions = {
  method?: string
  body?: unknown
  query?: Query
  /** Login/refresh send no bearer — they are how you get one. */
  anonymous?: boolean
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, query, anonymous = false } = opts

  const send = async (): Promise<Response> => {
    const headers: Record<string, string> = { 'X-Tenant-ID': TENANT }
    if (body !== undefined) headers['Content-Type'] = 'application/json'
    if (!anonymous) {
      const token = getTokens()?.access_token
      if (token) headers.Authorization = `Bearer ${token}`
    }
    return fetch(`${BASE_URL}${withQuery(path, query)}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  }

  let res = await send()

  // One transparent refresh, then retry. If the retry also 401s we surface it
  // rather than looping — the session is genuinely gone.
  if (res.status === 401 && !anonymous && (await refreshOnce())) {
    res = await send()
  }

  if (!res.ok) throw await toApiError(res)
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

/* ── typed helpers ──────────────────────────────────────────────────────────
 * `Ok<P, M, S>` pulls a response body for a path+method+status straight out of
 * the generated schema, so these return types track the backend automatically.
 */
type Ok<P extends keyof paths, M extends keyof paths[P], S extends number = 200> = paths[P][M] extends {
  responses: infer R
}
  ? S extends keyof R
    ? R[S] extends { content: { 'application/json': infer J } }
      ? J
      : never
    : never
  : never

export const api = {
  login: (email: string, password: string) =>
    request<Ok<'/api/v1/auth/login', 'post'>>('/api/v1/auth/login', {
      method: 'POST',
      body: { email, password },
      anonymous: true,
    }),

  me: () => request<Ok<'/api/v1/auth/me', 'get'>>('/api/v1/auth/me'),

  /** Returns a plain array, not a page. */
  listSports: (query?: { include_inactive?: boolean }) =>
    request<Ok<'/api/v1/sports', 'get'>>('/api/v1/sports', { query }),

  /** Plain array too. `at` asks for occupancy as of an instant. */
  listCourts: (query?: { sport_id?: string; at?: string }) =>
    request<Ok<'/api/v1/courts', 'get'>>('/api/v1/courts', { query }),

  /** The one paged endpoint of the three — `{ items, total, page, size, pages }`. */
  listBookings: (query?: {
    status?: string
    court_id?: string
    date_from?: string
    date_to?: string
    search?: string
    page?: number
    size?: number
  }) => request<Ok<'/api/v1/bookings', 'get'>>('/api/v1/bookings', { query }),

  /** Prices a draft without creating it. Court hire is rated server-side (peak,
   *  weekend), so the wizard has to ask rather than compute the total it is about
   *  to charge — this is what keeps the quote and the booking in agreement. */
  quoteBooking: (body: {
    court_id: string
    starts_at: string
    duration_min: number
    equipment?: { equipment_id: string; qty: number }[]
    discount?: number
  }) =>
    request<Ok<'/api/v1/bookings/quote', 'post'>>('/api/v1/bookings/quote', { method: 'POST', body }),

  /** 409 when any part of the slot is already taken — enforced by a Postgres
   *  exclusion constraint, so it is authoritative rather than a racy pre-check. */
  createBooking: (body: {
    court_id: string
    starts_at: string
    duration_min: number
    customer_id?: string
    customer_name?: string
    customer_phone?: string
    booking_type?: 'walkin' | 'online'
    equipment?: { equipment_id: string; qty: number }[]
    discount?: number
    notes?: string
  }) => request<Ok<'/api/v1/bookings', 'post', 201>>('/api/v1/bookings', { method: 'POST', body }),

  recordPayment: (body: {
    amount: number
    method: 'cash' | 'upi' | 'card' | 'bank' | 'cheque'
    booking_id?: string
    notes?: string
  }) => request<unknown>('/api/v1/payments', { method: 'POST', body }),

  listEquipment: (query?: {
    category?: string
    low_stock_only?: boolean
    sport_id?: string
    published_to_pos?: boolean
    page?: number
    size?: number
  }) => request<Ok<'/api/v1/equipment', 'get'>>('/api/v1/equipment', { query }),

  createEquipment: (body: {
    name: string
    category: string
    barcode: string
    rental_price?: number
    deposit?: number
    condition?: 'excellent' | 'good' | 'fair' | 'poor'
    low_stock_threshold?: number
    sport_id?: string | null
    published_to_pos?: boolean
    image_url?: string | null
    consumable?: boolean
    qty_stock?: number
  }) =>
    request<Ok<'/api/v1/equipment', 'post', 201>>('/api/v1/equipment', { method: 'POST', body }),

  updateEquipment: (
    equipmentId: string,
    body: Partial<{
      name: string
      category: string
      rental_price: number
      deposit: number
      condition: 'excellent' | 'good' | 'fair' | 'poor'
      low_stock_threshold: number
      sport_id: string | null
      published_to_pos: boolean
      image_url: string | null
      consumable: boolean
    }>,
  ) =>
    request<Ok<'/api/v1/equipment/{equipment_id}', 'patch'>>(`/api/v1/equipment/${equipmentId}`, {
      method: 'PATCH',
      body,
    }),

  deleteEquipment: (equipmentId: string) =>
    request<void>(`/api/v1/equipment/${equipmentId}`, { method: 'DELETE' }),

  createMovement: (
    equipmentId: string,
    body: {
      kind: 'issue' | 'return' | 'to_maintenance' | 'from_maintenance' | 'lost' | 'restock' | 'adjust' | 'write_off'
      qty: number
      booking_id?: string
      note?: string
    },
  ) =>
    request<Ok<'/api/v1/equipment/{equipment_id}/movements', 'post', 201>>(
      `/api/v1/equipment/${equipmentId}/movements`,
      { method: 'POST', body },
    ),

  listMovements: (equipmentId: string, query?: { page?: number; size?: number }) =>
    request<Ok<'/api/v1/equipment/{equipment_id}/movements', 'get'>>(
      `/api/v1/equipment/${equipmentId}/movements`,
      { query },
    ),
}

export { request, BASE_URL, TENANT }
