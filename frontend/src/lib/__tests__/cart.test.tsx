import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { CartProvider, MAX_QUANTITY_PER_SERVICE, useCart } from "@/lib/cart";

/**
 * The cart decides *how many distinct services* are selected, and that number
 * is what the multi-service discount turns on. It must never decide money.
 *
 * Driven through rendered controls rather than by reaching into the hook, so
 * these assertions survive a refactor of the internals.
 */

const A = "11111111-1111-4111-8111-111111111111";
const B = "22222222-2222-4222-8222-222222222222";

function Probe() {
  const cart = useCart();
  return (
    <div>
      <span data-testid="distinct">{cart.distinctCount}</span>
      <span data-testid="units">{cart.totalUnits}</span>
      <span data-testid="hydrated">{String(cart.hydrated)}</span>
      <span data-testid="qtyA">{cart.quantityOf(A)}</span>
      <span data-testid="keys">{Object.keys(cart).join(" ")}</span>
      <button onClick={() => cart.add(A)}>add A</button>
      <button onClick={() => cart.add(B)}>add B</button>
      <button onClick={() => cart.setQuantity(A, 0)}>zero A</button>
      <button onClick={() => cart.clear()}>clear</button>
    </div>
  );
}

function setup() {
  return render(
    <CartProvider>
      <Probe />
    </CartProvider>,
  );
}

const distinct = () => Number(screen.getByTestId("distinct").textContent);
const units = () => Number(screen.getByTestId("units").textContent);
const qtyA = () => Number(screen.getByTestId("qtyA").textContent);
const hydrated = () => screen.findByText("true");

beforeEach(() => {
  window.localStorage.clear();
});

describe("cart", () => {
  it("counts distinct services, not units", async () => {
    const user = userEvent.setup();
    setup();
    await hydrated();

    await user.click(screen.getByText("add A"));
    await user.click(screen.getByText("add A"));
    await user.click(screen.getByText("add A"));

    // Three haircuts is one service: this is what keeps quantity from
    // unlocking the multi-service discount.
    expect(distinct()).toBe(1);
    expect(units()).toBe(3);
  });

  it("counts two different services as two", async () => {
    const user = userEvent.setup();
    setup();
    await hydrated();

    await user.click(screen.getByText("add A"));
    await user.click(screen.getByText("add B"));

    expect(distinct()).toBe(2);
    expect(units()).toBe(2);
  });

  it("caps quantity per service", async () => {
    const user = userEvent.setup();
    setup();
    await hydrated();

    for (let i = 0; i < MAX_QUANTITY_PER_SERVICE + 3; i++) {
      await user.click(screen.getByText("add A"));
    }
    expect(qtyA()).toBe(MAX_QUANTITY_PER_SERVICE);
  });

  it("removes the line when quantity drops below one", async () => {
    const user = userEvent.setup();
    setup();
    await hydrated();

    await user.click(screen.getByText("add A"));
    await user.click(screen.getByText("zero A"));

    expect(distinct()).toBe(0);
    expect(qtyA()).toBe(0);
  });

  it("clears everything", async () => {
    const user = userEvent.setup();
    setup();
    await hydrated();

    await user.click(screen.getByText("add A"));
    await user.click(screen.getByText("add B"));
    await user.click(screen.getByText("clear"));

    expect(distinct()).toBe(0);
  });

  it("exposes no money at all", async () => {
    setup();
    await hydrated();
    // Guards the invariant: if a price ever appears on the cart API there are
    // two sources of truth for what a customer owes. "totalUnits" is a count,
    // so the check names money terms specifically.
    const keys = screen.getByTestId("keys").textContent?.toLowerCase() ?? "";
    expect(keys).not.toMatch(/paise|price|discount|amount|rupee|subtotal|payable/);
  });

  it("restores a selection from storage", async () => {
    window.localStorage.setItem(
      "salon.cart.v1",
      JSON.stringify([{ serviceId: A, quantity: 2 }]),
    );
    setup();
    await hydrated();

    expect(qtyA()).toBe(2);
  });

  it("ignores corrupt stored data instead of crashing", async () => {
    window.localStorage.setItem("salon.cart.v1", "{not json");
    setup();
    await hydrated();

    expect(distinct()).toBe(0);
  });

  it("drops malformed entries and clamps absurd quantities", async () => {
    window.localStorage.setItem(
      "salon.cart.v1",
      JSON.stringify([
        { serviceId: A, quantity: 9999 },
        { serviceId: 42, quantity: 1 },
        { nope: true },
      ]),
    );
    setup();
    await hydrated();

    expect(distinct()).toBe(1);
    expect(qtyA()).toBe(MAX_QUANTITY_PER_SERVICE);
  });
});
