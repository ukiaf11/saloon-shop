/**
 * The payment panel in each state the API can put an order in. The panel must
 * show what the order says -- a claim is never shown as paid, and a draw
 * result never appears before the salon has confirmed the money.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { orderSchema, type Order } from "@/types/api";

import { UpiPaymentPanel } from "../upi-payment";

const UPI = {
  qr_image_version: "abc123",
  upi_id: "salon@okaxis",
  payee_name: "Upendra Salon",
};

/** Shaped exactly like the API's serialize_order, and parsed to prove it. */
function order(overrides: Partial<Order> = {}): Order {
  return orderSchema.parse({
    id: "8b1f2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
    public_order_number: "SL-260922-ABCD",
    status: "DRAFT",
    currency: "INR",
    subtotal_paise: 45000,
    discount_percent_applied: 10,
    discount_paise: 4500,
    total_paise: 40500,
    created_at: "2026-09-22T05:00:00Z",
    customer: { name: "Rahul", phone_masked: "90******01" },
    items: [
      {
        service_name: "Hair Cutting",
        unit_price_paise: 30000,
        quantity: 1,
        line_total_paise: 30000,
        discount_alloc_paise: 3000,
        net_paid_paise: 27000,
      },
    ],
    paid_at: null,
    payment: {
      status: "not_started",
      method: null,
      reference_last4: null,
      rejection_reason: null,
      submitted_at: null,
      decided_at: null,
    },
    lucky: {
      status: "pending",
      reason: null,
      participant_number: null,
      campaign_date: null,
      refund_paise: 0,
      refund_status: null,
      free_services: [],
    },
    ...overrides,
  });
}

const noop = () => undefined;

afterEach(() => {
  vi.restoreAllMocks();
});

describe("UpiPaymentPanel", () => {
  it("shows the QR, the exact amount and a one-tap UPI link before payment", () => {
    render(
      <UpiPaymentPanel order={order()} upi={UPI} headingId="t" onOrderChange={noop} />,
    );

    expect(screen.getByRole("heading", { name: "Pay ₹405 by UPI" })).toBeTruthy();
    const qr = screen.getByRole("img", { name: /UPI QR code to pay Upendra Salon/ });
    expect(qr.getAttribute("src")).toContain("/payments/qr-image?v=abc123");
    expect(screen.getByRole("link", { name: /Open UPI app/ }).getAttribute("href")).toBe(
      "upi://pay?pa=salon%40okaxis&pn=Upendra%20Salon&am=405.00&cu=INR&tn=SL-260922-ABCD",
    );
  });

  it("has no UPI link when the owner gave no UPI ID", () => {
    render(
      <UpiPaymentPanel
        order={order()}
        upi={{ ...UPI, upi_id: null }}
        headingId="t"
        onOrderChange={noop}
      />,
    );
    expect(screen.queryByRole("link", { name: /Open UPI app/ })).toBeNull();
  });

  it("checks the reference before sending it", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    render(
      <UpiPaymentPanel order={order()} upi={UPI} headingId="t" onOrderChange={noop} />,
    );

    await userEvent.type(screen.getByLabelText(/UPI reference number/), "12345");
    await userEvent.click(screen.getByRole("button", { name: /I've paid ₹405/ }));

    expect(screen.getByRole("alert").textContent).toMatch(/12-digit UPI reference/);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("says a claim is being checked, not that it is paid", () => {
    render(
      <UpiPaymentPanel
        order={order({
          status: "PAYMENT_PENDING",
          payment: {
            status: "awaiting_confirmation",
            method: "upi_qr",
            reference_last4: "9012",
            rejection_reason: null,
            submitted_at: "2026-09-22T05:01:00Z",
            decided_at: null,
          },
          lucky: { ...order().lucky, status: "held", campaign_date: "2026-09-22" },
        })}
        upi={UPI}
        headingId="t"
        onOrderChange={noop}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "Payment sent for checking" }),
    ).toBeTruthy();
    expect(screen.getByText(/place in today's lucky draw is held/)).toBeTruthy();
    expect(screen.getByText("9012")).toBeTruthy();
    expect(screen.queryByText(/won/i)).toBeNull();
  });

  it("shows a win with the refund and the free services", () => {
    render(
      <UpiPaymentPanel
        order={order({
          status: "REFUND_PENDING",
          paid_at: "2026-09-22T05:05:00Z",
          payment: { ...order().payment, status: "confirmed", method: "upi_qr" },
          lucky: {
            status: "won",
            reason: null,
            participant_number: 3,
            campaign_date: "2026-09-22",
            refund_paise: 27000,
            refund_status: "pending",
            free_services: ["Shaving", "Face Massage"],
          },
        })}
        upi={UPI}
        headingId="t"
        onOrderChange={noop}
      />,
    );
    expect(screen.getByRole("heading", { name: "You won a lucky slot!" })).toBeTruthy();
    expect(screen.getByText("#3")).toBeTruthy();
    expect(screen.getByText(/Free for you: Shaving, Face Massage/)).toBeTruthy();
    expect(screen.getByText(/will refund ₹270/)).toBeTruthy();
  });

  it("explains a paid booking that is not in the draw", () => {
    render(
      <UpiPaymentPanel
        order={order({
          status: "PAID",
          payment: { ...order().payment, status: "confirmed", method: "upi_qr" },
          lucky: { ...order().lucky, status: "not_entered", reason: "REPEAT_ENTRY" },
        })}
        upi={UPI}
        headingId="t"
        onOrderChange={noop}
      />,
    );
    expect(screen.getByRole("heading", { name: "Payment confirmed" })).toBeTruthy();
    expect(screen.getByText(/already has an entry in today's lucky draw/)).toBeTruthy();
  });

  it("tells the customer when the salon could not find their payment", () => {
    render(
      <UpiPaymentPanel
        order={order({
          status: "PAYMENT_FAILED",
          payment: {
            ...order().payment,
            status: "rejected",
            method: "upi_qr",
            rejection_reason: "No payment with this reference",
          },
        })}
        upi={UPI}
        headingId="t"
        onOrderChange={noop}
      />,
    );
    expect(screen.getByRole("alert").textContent).toMatch(
      /could not find your earlier payment/,
    );
    expect(screen.getByRole("alert").textContent).toMatch(
      /No payment with this reference/,
    );
  });
});
