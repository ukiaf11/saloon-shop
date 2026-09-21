"use client";

/**
 * Customer-side payment calls. Like lib/orders, these fail loudly: a swallowed
 * error here could let someone believe their payment was recorded when it was
 * not.
 */

import { API_BASE_URL, apiRequest } from "@/lib/api";
import {
  orderSchema,
  paymentOptionsSchema,
  type Order,
  type PaymentOptions,
} from "@/types/api";

/** How the customer can pay right now. Never cached: the owner can switch the
 * QR on or off at any moment. */
export async function fetchPaymentOptions(signal?: AbortSignal): Promise<PaymentOptions> {
  return apiRequest("/payments/options", paymentOptionsSchema, {
    credentials: "omit",
    cache: "no-store",
    signal,
  });
}

export async function fetchOrder(orderId: string, signal?: AbortSignal): Promise<Order> {
  return apiRequest(`/orders/${encodeURIComponent(orderId)}`, orderSchema, {
    credentials: "omit",
    cache: "no-store",
    signal,
  });
}

/** "I have paid, here is my UPI reference." Resubmitting corrects a typo. */
export async function submitUpiReference(
  orderId: string,
  reference: string,
): Promise<Order> {
  return apiRequest(`/orders/${encodeURIComponent(orderId)}/upi-payment`, orderSchema, {
    method: "POST",
    body: { reference },
    credentials: "omit",
    cache: "no-store",
  });
}

/** The versioned QR URL: it changes exactly when the owner uploads a new QR. */
export function qrImageUrl(version: string): string {
  return `${API_BASE_URL}/payments/qr-image?v=${encodeURIComponent(version)}`;
}

const LAST_ORDER_KEY = "salon:last-order";

export type RememberedOrder = { id: string; number: string };

/**
 * The customer's latest order, kept in this browser so they can come back to
 * see whether their payment was confirmed. Storage can be unavailable (private
 * mode, blocked site data), which must never break checkout.
 */
export function rememberOrder(order: RememberedOrder): void {
  try {
    localStorage.setItem(LAST_ORDER_KEY, JSON.stringify(order));
  } catch {
    // Best effort only.
  }
}

export function recallOrder(): RememberedOrder | null {
  try {
    const raw = localStorage.getItem(LAST_ORDER_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (
      parsed &&
      typeof parsed === "object" &&
      typeof (parsed as RememberedOrder).id === "string" &&
      typeof (parsed as RememberedOrder).number === "string"
    ) {
      return parsed as RememberedOrder;
    }
  } catch {
    // Fall through.
  }
  return null;
}
