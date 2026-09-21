"use client";

/**
 * Client-side calls to the quote and order endpoints.
 *
 * These run in the browser during checkout, so unlike the marketing readers in
 * `site-data.ts` they must **fail loudly**. Swallowing an error here would let
 * someone believe they had a price, or an order, that does not exist.
 */

import { apiRequest } from "@/lib/api";
import type { CartLine } from "@/lib/cart";
import { orderSchema, quoteSchema, type Order, type Quote } from "@/types/api";

function toItems(lines: CartLine[]) {
  return lines.map((l) => ({ service_id: l.serviceId, quantity: l.quantity }));
}

/** Price a basket. Advisory -- the server recomputes when the order is placed. */
export async function fetchQuote(
  lines: CartLine[],
  signal?: AbortSignal,
): Promise<Quote> {
  return apiRequest("/orders/quote", quoteSchema, {
    method: "POST",
    body: { items: toItems(lines) },
    credentials: "omit",
    signal,
    // Pricing must never be served from a cache: the owner can change a price
    // at any moment and a stale quote is a wrong quote.
    cache: "no-store",
  });
}

export type CustomerDetails = {
  name: string;
  phone: string;
  email?: string;
};

/**
 * Place the order.
 *
 * `idempotencyKey` is generated once per checkout attempt by the caller and
 * reused across retries, so a double-submit or a retried network failure
 * cannot produce two orders for one customer.
 */
export async function createOrder(
  lines: CartLine[],
  customer: CustomerDetails,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<Order> {
  return apiRequest("/orders", orderSchema, {
    method: "POST",
    body: {
      items: toItems(lines),
      customer: {
        name: customer.name,
        phone: customer.phone,
        ...(customer.email ? { email: customer.email } : {}),
      },
    },
    credentials: "omit",
    signal,
    cache: "no-store",
    idempotencyKey,
  });
}

/** A key that survives retries of the same checkout attempt. */
export function newIdempotencyKey(): string {
  return globalThis.crypto?.randomUUID
    ? globalThis.crypto.randomUUID()
    : `k-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
