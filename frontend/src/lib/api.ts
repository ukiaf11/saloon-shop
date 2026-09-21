/**
 * Typed API client.
 *
 * Every response is parsed through a Zod schema before it reaches a component,
 * so a backend contract change surfaces as a clear error rather than an
 * undefined deep in the render tree.
 *
 * Errors arrive in the envelope the backend's common.exceptions handler emits:
 *   { error: { code, message, request_id } }
 * The machine-readable `code` is what UI should branch on -- never the message.
 */

import { z } from "zod";

/**
 * `??` is wrong here: a CI job that passes an unset repository variable sets
 * the value to an empty string, not undefined, which would make every request
 * URL relative and hang the build. Treat blank as unset.
 */
const PUBLIC_API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || "http://localhost:8000/api/v1";

/**
 * Server-side override, deliberately NOT prefixed NEXT_PUBLIC_ so it is never
 * inlined into the browser bundle.
 *
 * Two different callers need two different addresses. Server rendering (and the
 * static export's build step) can reach the API over a private network -- the
 * GitHub Pages build talks to a backend running inside the CI job, and on
 * Railway it can use the internal hostname. The browser needs the public URL.
 * With a single variable, the Pages build baked the CI job's 127.0.0.1 into the
 * bundle and every visitor's browser tried to call its own localhost.
 */
const INTERNAL_API_BASE_URL = process.env.API_INTERNAL_URL?.trim();

export const API_BASE_URL =
  typeof window === "undefined" && INTERNAL_API_BASE_URL
    ? INTERNAL_API_BASE_URL
    : PUBLIC_API_BASE_URL;

/**
 * False on a static preview that has no public API behind it (GitHub Pages
 * before a backend is deployed). Booking and live counters then stand down
 * instead of calling an address that cannot answer.
 */
export const BOOKING_ENABLED = process.env.NEXT_PUBLIC_BOOKING_ENABLED !== "0";

/**
 * No request may hang indefinitely. A static export fetches at build time, and
 * an unreachable API without this stalls the build until the framework's own
 * 60s-per-page timeout fires on every retry, turning a degraded build into a
 * failed one.
 */
export const DEFAULT_TIMEOUT_MS = 10_000;

export const apiErrorSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    request_id: z.string().nullable().optional(),
  }),
});

export class ApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
    readonly requestId?: string | null,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** True when today's promotional capacity is exhausted. */
  get isCapacityExhausted(): boolean {
    return this.code === "capacity_exhausted";
  }
}

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
  /** Forward the CSRF token on mutating admin requests. */
  csrfToken?: string;
  /**
   * Sent as `Idempotency-Key`. Reuse the same value across retries of one
   * logical attempt so a double-submit cannot create two orders.
   */
  idempotencyKey?: string;
  /**
   * Next.js fetch caching. Public marketing reads pass a `revalidate` window
   * and a tag so an owner's edit can be pushed through with `revalidateTag`
   * instead of waiting for a rebuild. Without this, Next caches the response
   * persistently with no handle to invalidate it.
   */
  next?: { revalidate?: number | false; tags?: string[] };
  cache?: RequestCache;
  /** Abort after this many ms. Defaults to DEFAULT_TIMEOUT_MS. */
  timeoutMs?: number;
  /**
   * Cookies are required for admin session auth, which is cross-origin, so
   * "include" stays the default. Public read endpoints pass "omit": they are
   * unauthenticated, and sending credentials narrows what Next will cache.
   */
  credentials?: RequestCredentials;
};

export async function apiRequest<T>(
  path: string,
  schema: z.ZodType<T>,
  {
    method = "GET",
    body,
    signal,
    csrfToken,
    idempotencyKey,
    next,
    cache,
    credentials = "include",
    timeoutMs = DEFAULT_TIMEOUT_MS,
  }: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (csrfToken) headers["X-CSRFToken"] = csrfToken;
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;

  // Combine the caller's signal with the timeout so either can abort.
  const timeoutSignal = AbortSignal.timeout(timeoutMs);
  const effectiveSignal = signal
    ? AbortSignal.any([signal, timeoutSignal])
    : timeoutSignal;

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials,
    signal: effectiveSignal,
    ...(next ? { next } : {}),
    ...(cache ? { cache } : {}),
  });

  const text = await response.text();
  const payload: unknown = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const parsed = apiErrorSchema.safeParse(payload);
    if (parsed.success) {
      throw new ApiError(
        parsed.data.error.code,
        parsed.data.error.message,
        response.status,
        parsed.data.error.request_id,
      );
    }
    throw new ApiError(
      "request_failed",
      `Request failed (${response.status})`,
      response.status,
    );
  }

  const result = schema.safeParse(payload);
  if (!result.success) {
    throw new ApiError(
      "invalid_response",
      `Unexpected response shape for ${path}: ${result.error.message}`,
      response.status,
    );
  }
  return result.data;
}
