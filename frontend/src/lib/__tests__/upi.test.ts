import { describe, expect, it } from "vitest";

import {
  formatUtr,
  isValidUtr,
  normaliseUtr,
  paiseToUpiAmount,
  upiPayLink,
} from "@/lib/upi";

describe("paiseToUpiAmount", () => {
  it.each([
    [40500, "405.00"],
    [99999, "999.99"],
    [5, "0.05"],
    [0, "0.00"],
    [12345678, "123456.78"],
  ])("%i paise -> %s", (paise, expected) => {
    expect(paiseToUpiAmount(paise)).toBe(expected);
  });

  it("refuses fractions and negatives rather than guessing", () => {
    expect(() => paiseToUpiAmount(1.5)).toThrow(RangeError);
    expect(() => paiseToUpiAmount(-1)).toThrow(RangeError);
  });
});

describe("upiPayLink", () => {
  it("fills in payee, exact amount, currency and the order number", () => {
    expect(
      upiPayLink({
        upiId: "salon@okaxis",
        payeeName: "Upendra Salon",
        amountPaise: 40500,
        note: "SL-260922-ABCD",
      }),
    ).toBe(
      "upi://pay?pa=salon%40okaxis&pn=Upendra%20Salon&am=405.00&cu=INR&tn=SL-260922-ABCD",
    );
  });

  it("encodes spaces as %20, never +, which some UPI apps show literally", () => {
    const link = upiPayLink({
      upiId: "a.b@ybl",
      payeeName: "A & B Salon",
      amountPaise: 100,
    });
    expect(link).toContain("pn=A%20%26%20B%20Salon");
    expect(link).not.toContain("+");
  });

  it("leaves out an absent payee name and note", () => {
    expect(upiPayLink({ upiId: "a.b@ybl", amountPaise: 100 })).toBe(
      "upi://pay?pa=a.b%40ybl&am=1.00&cu=INR",
    );
  });
});

describe("UTR handling", () => {
  it("accepts 12 digits, with the spaces and dashes people type", () => {
    expect(isValidUtr("412356789012")).toBe(true);
    expect(isValidUtr("4123 5678 9012")).toBe(true);
    expect(isValidUtr("4123-5678-9012")).toBe(true);
    expect(normaliseUtr(" 4123 5678-9012 ")).toBe("412356789012");
  });

  it.each(["", "12345", "1234567890123", "41235678901a", "4123.5678.9012"])(
    "rejects %j",
    (value) => {
      expect(isValidUtr(value)).toBe(false);
    },
  );

  it("groups a reference in fours for reading against a banking app", () => {
    expect(formatUtr("412356789012")).toBe("4123 5678 9012");
  });
});
