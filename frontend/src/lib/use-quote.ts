"use client";

/**
 * Live pricing for the current selection.
 *
 * Debounced, because a customer tapping Add three times should cost one
 * request, not three. Every superseded request is aborted so a slow early
 * response can never overwrite a newer price — a stale total on screen is how
 * someone ends up believing they owe the wrong amount.
 *
 * The result is stored *with the selection it belongs to*. Anything that does
 * not match the current selection is reported as loading rather than shown,
 * which is what stops the previous basket's total flashing up while the new
 * one is still in flight. It also means the hook never has to setState during
 * an effect to clear itself.
 */

import { useEffect, useState } from "react";

import { ApiError } from "@/lib/api";
import type { CartLine } from "@/lib/cart";
import { fetchQuote } from "@/lib/orders";
import type { Quote } from "@/types/api";

const DEBOUNCE_MS = 300;

export type QuoteState = {
  quote: Quote | null;
  /** True while the displayed price does not yet match the selection. */
  loading: boolean;
  error: string | null;
  /** Machine-readable code, for branching. Never branch on the message. */
  errorCode: string | null;
};

const EMPTY: QuoteState = {
  quote: null,
  loading: false,
  error: null,
  errorCode: null,
};

type Resolved = QuoteState & { key: string };

/** Stable identity for a selection, order-independent. */
function selectionKey(lines: CartLine[]): string {
  return JSON.stringify(
    [...lines].sort((a, b) => a.serviceId.localeCompare(b.serviceId)),
  );
}

export function useQuote(lines: CartLine[]): QuoteState {
  const key = selectionKey(lines);
  const isEmpty = lines.length === 0;

  const [resolved, setResolved] = useState<Resolved | null>(null);

  useEffect(() => {
    if (isEmpty) return;

    const parsed: CartLine[] = JSON.parse(key);
    const controller = new AbortController();

    const timer = setTimeout(() => {
      fetchQuote(parsed, controller.signal)
        .then((quote) => {
          if (controller.signal.aborted) return;
          setResolved({ key, quote, loading: false, error: null, errorCode: null });
        })
        .catch((err: unknown) => {
          if (controller.signal.aborted) return;
          setResolved({
            key,
            // No stale price is left on screen after the server disagreed.
            quote: null,
            loading: false,
            error:
              err instanceof ApiError
                ? err.message
                : "We could not price your selection. Please try again.",
            errorCode: err instanceof ApiError ? err.code : "request_failed",
          });
        });
    }, DEBOUNCE_MS);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [key, isEmpty]);

  if (isEmpty) return EMPTY;

  // Derived, not stored: a result for a different selection is by definition
  // not the current price, so the UI shows "pricing" instead of a wrong number.
  if (!resolved || resolved.key !== key) {
    return { quote: null, loading: true, error: null, errorCode: null };
  }
  return resolved;
}
