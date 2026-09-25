/**
 * A browser's saved cart can hold a service the salon has since hidden. The
 * server refuses the whole basket, and that service's card no longer renders
 * -- so the tray itself must offer the way out, or the customer can never
 * check out again in that browser.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CartProvider } from "@/lib/cart";

import { SelectionCart } from "../selection-cart";

const LIVE = "11111111-1111-4111-8111-111111111111";
const RETIRED = "22222222-2222-4222-8222-222222222222";

function quoteFor(serviceIds: string[]) {
  return {
    currency: "INR",
    subtotal_paise: 30000,
    discount_percent: 0,
    configured_discount_percent: 10,
    discount_paise: 0,
    payable_paise: 30000,
    eligible_for_discount: false,
    distinct_service_count: serviceIds.length,
    min_distinct_services: 2,
    expires_at: "2026-09-25T12:00:00Z",
    lines: serviceIds.map((id) => ({
      service_id: id,
      name: "Hair Cutting",
      unit_price_paise: 30000,
      quantity: 1,
      line_total_paise: 30000,
      discount_alloc_paise: 0,
      net_paid_paise: 30000,
    })),
  };
}

beforeEach(() => {
  window.localStorage.setItem(
    "salon.cart.v1",
    JSON.stringify([
      { serviceId: LIVE, quantity: 1 },
      { serviceId: RETIRED, quantity: 1 },
    ]),
  );
  vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, init) => {
    const body = JSON.parse(String((init as RequestInit).body)) as {
      items: { service_id: string }[];
    };
    const ids = body.items.map((i) => i.service_id);
    if (ids.includes(RETIRED)) {
      return new Response(
        JSON.stringify({
          error: {
            code: "service_unavailable_for_order",
            message: "One or more selected services are no longer available.",
            request_id: null,
            details: { unavailable_service_ids: [RETIRED] },
          },
        }),
        { status: 400 },
      );
    }
    return new Response(JSON.stringify(quoteFor(ids)), { status: 200 });
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe("SelectionCart with a retired service in the saved cart", () => {
  it("offers to remove it, then prices what is left", async () => {
    render(
      <CartProvider>
        <SelectionCart />
      </CartProvider>,
    );

    const remove = await screen.findByRole(
      "button",
      { name: "Remove unavailable" },
      {
        timeout: 3000,
      },
    );
    expect(
      (screen.getByRole("button", { name: "Continue" }) as HTMLButtonElement).disabled,
    ).toBe(true);

    await userEvent.click(remove);

    await waitFor(
      () =>
        expect(
          (screen.getByRole("button", { name: "Continue" }) as HTMLButtonElement)
            .disabled,
        ).toBe(false),
      { timeout: 3000 },
    );
    expect(JSON.parse(window.localStorage.getItem("salon.cart.v1") ?? "[]")).toEqual([
      { serviceId: LIVE, quantity: 1 },
    ]);
  });
});
