"use client";

/**
 * Owner-panel API calls.
 *
 * The session token lives in sessionStorage: it survives a reload but not
 * closing the tab, which suits a panel the owner opens on their own phone.
 * Every call here carries it as a bearer header and nothing is cached.
 */

import type { z } from "zod";

import { ApiError, apiRequest } from "@/lib/api";
import {
  meSchema,
  okSchema,
  ownerPaymentListSchema,
  ownerPaymentSchema,
  ownerServiceListSchema,
  ownerServiceSchema,
  ownerRefundListSchema,
  ownerRefundSchema,
  paymentSettingsSchema,
  sessionSchema,
  type OwnerPayment,
  type OwnerRefund,
  type OwnerService,
  type PaymentSettings,
} from "@/types/owner";

const TOKEN_KEY = "salon.owner.session";

// The token is an external store, read with useSyncExternalStore, so signing
// in or out anywhere re-renders whatever depends on it. `memory` covers a
// browser where sessionStorage is unavailable: the session then lasts until
// the page is reloaded.
let memory: string | null = null;
const listeners = new Set<() => void>();

function notify(): void {
  listeners.forEach((listener) => listener());
}

export function subscribeToken(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function loadToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY) ?? memory;
  } catch {
    return memory;
  }
}

export function saveToken(token: string): void {
  memory = token;
  try {
    sessionStorage.setItem(TOKEN_KEY, token);
  } catch {
    // Falls back to memory.
  }
  notify();
}

export function clearToken(): void {
  memory = null;
  try {
    sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // Nothing to clear.
  }
  notify();
}

/** The session is gone (expired, revoked, or the account locked). */
export class SessionEnded extends Error {
  constructor() {
    super("Your session has ended. Please sign in again.");
    this.name = "SessionEnded";
  }
}

type Options = {
  method?: "GET" | "POST" | "PUT" | "PATCH";
  body?: unknown;
};

async function ownerCall<T>(
  token: string,
  path: string,
  schema: z.ZodType<T>,
  { method = "GET", body }: Options = {},
): Promise<T> {
  try {
    return await apiRequest(path, schema, {
      method,
      body,
      authToken: token,
      credentials: "omit",
      cache: "no-store",
      // Uploads over a slow mobile connection need longer than a JSON read.
      timeoutMs: body instanceof FormData ? 60_000 : 15_000,
    });
  } catch (error) {
    // A wrong password on a re-authenticated action is a 403, so any 401 here
    // really does mean the session is over.
    if (error instanceof ApiError && error.status === 401) {
      clearToken();
      throw new SessionEnded();
    }
    throw error;
  }
}

/** A message fit to show the owner for anything a call can throw. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof SessionEnded) return error.message;
  if (error instanceof DOMException && error.name === "TimeoutError") {
    return "The server took too long to answer. Check your connection and try again.";
  }
  return "Something went wrong. Check your connection and try again.";
}

export async function signIn(email: string, password: string) {
  return apiRequest("/auth/login", sessionSchema, {
    method: "POST",
    body: { email, password },
    credentials: "omit",
    cache: "no-store",
  });
}

export const getMe = (token: string) => ownerCall(token, "/auth/me", meSchema);

export const signOut = (token: string) =>
  ownerCall(token, "/auth/logout", okSchema, { method: "POST" });

export const changePassword = (token: string, current: string, next: string) =>
  ownerCall(token, "/auth/password", okSchema, {
    method: "POST",
    body: { current_password: current, new_password: next },
  });

export const getPaymentSettings = (token: string): Promise<PaymentSettings> =>
  ownerCall(token, "/owner/payment-settings", paymentSettingsSchema);

export const savePaymentSettings = (
  token: string,
  form: FormData,
): Promise<PaymentSettings> =>
  ownerCall(token, "/owner/payment-settings", paymentSettingsSchema, {
    method: "PUT",
    body: form,
  });

export type PaymentListStatus = "awaiting" | "confirmed" | "rejected";

export const listPayments = async (
  token: string,
  status: PaymentListStatus,
): Promise<OwnerPayment[]> =>
  (await ownerCall(token, `/owner/payments?status=${status}`, ownerPaymentListSchema))
    .results;

/**
 * `reference` is the UPI reference the owner checked. The server refuses the
 * decision if the customer has changed it since this list loaded.
 */
export const confirmPayment = (
  token: string,
  id: string,
  reference: string,
): Promise<OwnerPayment> =>
  ownerCall(token, `/owner/payments/${id}/confirm`, ownerPaymentSchema, {
    method: "POST",
    body: { reference },
  });

export const rejectPayment = (
  token: string,
  id: string,
  reference: string,
  reason: string,
): Promise<OwnerPayment> =>
  ownerCall(token, `/owner/payments/${id}/reject`, ownerPaymentSchema, {
    method: "POST",
    body: { reference, reason },
  });

export const listRefunds = async (
  token: string,
  status: "pending" | "sent",
): Promise<OwnerRefund[]> =>
  (await ownerCall(token, `/owner/refunds?status=${status}`, ownerRefundListSchema))
    .results;

export const markRefundSent = (
  token: string,
  id: string,
  method: "UPI" | "CASH",
  reference: string,
): Promise<OwnerRefund> =>
  ownerCall(token, `/owner/refunds/${id}/mark-sent`, ownerRefundSchema, {
    method: "POST",
    body: { method, reference },
  });

export const listOwnerServices = async (token: string): Promise<OwnerService[]> =>
  (await ownerCall(token, "/owner/services", ownerServiceListSchema)).results;

export const changeServicePrice = (
  token: string,
  id: string,
  pricePaise: number,
  reason: string,
): Promise<OwnerService> =>
  ownerCall(token, `/owner/services/${id}/price`, ownerServiceSchema, {
    method: "POST",
    body: { price_paise: pricePaise, ...(reason ? { reason } : {}) },
  });

export const updateOwnerService = (
  token: string,
  id: string,
  patch: Partial<
    Pick<OwnerService, "is_active" | "is_featured" | "duration_minutes" | "description">
  >,
): Promise<OwnerService> =>
  ownerCall(token, `/owner/services/${id}`, ownerServiceSchema, {
    method: "PATCH",
    body: patch,
  });
