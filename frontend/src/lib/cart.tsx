"use client";

/**
 * Service selection state.
 *
 * The cart holds service ids and quantities. It deliberately holds **no
 * money**: prices, the discount and the total all come from the server's quote
 * (`src/lib/orders.ts`). If this file ever starts adding up rupees, there are
 * two sources of truth for what a customer owes, and the browser's copy is the
 * one an attacker controls.
 *
 * Selection survives a reload via localStorage, because losing a half-built
 * basket to an accidental refresh is a real way to lose a booking. The stored
 * value is per-viewer and non-authoritative; service ids are re-validated by
 * the server on every quote, so a stale or edited entry fails cleanly.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  type ReactNode,
} from "react";

const STORAGE_KEY = "salon.cart.v1";
export const MAX_QUANTITY_PER_SERVICE = 10;

export type CartLine = { serviceId: string; quantity: number };
type CartState = { lines: CartLine[]; hydrated: boolean };

type CartAction =
  | { type: "add"; serviceId: string }
  | { type: "remove"; serviceId: string }
  | { type: "setQuantity"; serviceId: string; quantity: number }
  | { type: "clear" }
  | { type: "hydrate"; lines: CartLine[] };

function reducer(state: CartState, action: CartAction): CartState {
  switch (action.type) {
    case "hydrate":
      return { lines: action.lines, hydrated: true };

    case "add": {
      const existing = state.lines.find((l) => l.serviceId === action.serviceId);
      if (!existing) {
        return {
          ...state,
          lines: [...state.lines, { serviceId: action.serviceId, quantity: 1 }],
        };
      }
      if (existing.quantity >= MAX_QUANTITY_PER_SERVICE) return state;
      return {
        ...state,
        lines: state.lines.map((l) =>
          l.serviceId === action.serviceId ? { ...l, quantity: l.quantity + 1 } : l,
        ),
      };
    }

    case "remove":
      return {
        ...state,
        lines: state.lines.filter((l) => l.serviceId !== action.serviceId),
      };

    case "setQuantity": {
      if (action.quantity < 1) {
        return {
          ...state,
          lines: state.lines.filter((l) => l.serviceId !== action.serviceId),
        };
      }
      const quantity = Math.min(action.quantity, MAX_QUANTITY_PER_SERVICE);
      return {
        ...state,
        lines: state.lines.map((l) =>
          l.serviceId === action.serviceId ? { ...l, quantity } : l,
        ),
      };
    }

    case "clear":
      return { ...state, lines: [] };
  }
}

type CartContextValue = {
  lines: CartLine[];
  /** False until localStorage has been read, so the UI can avoid a flash. */
  hydrated: boolean;
  /** Distinct services, which is what the multi-service discount counts. */
  distinctCount: number;
  totalUnits: number;
  quantityOf: (serviceId: string) => number;
  add: (serviceId: string) => void;
  remove: (serviceId: string) => void;
  setQuantity: (serviceId: string, quantity: number) => void;
  clear: () => void;
};

const CartContext = createContext<CartContextValue | null>(null);

function readStored(): CartLine[] {
  // Every access is guarded: localStorage throws in a private window with site
  // data blocked, and a cart is not worth taking the page down for.
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter(
        (l): l is CartLine =>
          typeof l === "object" &&
          l !== null &&
          typeof (l as CartLine).serviceId === "string" &&
          Number.isInteger((l as CartLine).quantity),
      )
      .map((l) => ({
        serviceId: l.serviceId,
        quantity: Math.min(Math.max(l.quantity, 1), MAX_QUANTITY_PER_SERVICE),
      }))
      .slice(0, 20);
  } catch {
    return [];
  }
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, { lines: [], hydrated: false });

  // Hydrate after mount rather than in the initializer: reading localStorage
  // during render would make the server and client markup disagree.
  useEffect(() => {
    dispatch({ type: "hydrate", lines: readStored() });
  }, []);

  useEffect(() => {
    if (!state.hydrated) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state.lines));
    } catch {
      // Storage full or blocked. The cart still works for this page view.
    }
  }, [state.lines, state.hydrated]);

  const quantityOf = useCallback(
    (serviceId: string) =>
      state.lines.find((l) => l.serviceId === serviceId)?.quantity ?? 0,
    [state.lines],
  );

  const value = useMemo<CartContextValue>(
    () => ({
      lines: state.lines,
      hydrated: state.hydrated,
      distinctCount: state.lines.length,
      totalUnits: state.lines.reduce((sum, l) => sum + l.quantity, 0),
      quantityOf,
      add: (serviceId) => dispatch({ type: "add", serviceId }),
      remove: (serviceId) => dispatch({ type: "remove", serviceId }),
      setQuantity: (serviceId, quantity) =>
        dispatch({ type: "setQuantity", serviceId, quantity }),
      clear: () => dispatch({ type: "clear" }),
    }),
    [state.lines, state.hydrated, quantityOf],
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartContextValue {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used inside a CartProvider");
  return ctx;
}
