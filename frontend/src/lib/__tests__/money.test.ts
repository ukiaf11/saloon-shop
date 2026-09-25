import { describe, expect, it } from "vitest";

import { formatInr, rupeesToPaise } from "../money";

describe("formatInr", () => {
  it("renders whole rupees without decimals", () => {
    expect(formatInr(30000)).toBe("₹300");
    expect(formatInr(40500)).toBe("₹405");
  });

  it("renders paise remainders", () => {
    expect(formatInr(99)).toBe("₹0.99");
    expect(formatInr(30050)).toBe("₹300.50");
  });

  it("uses Indian digit grouping, matching the backend", () => {
    expect(formatInr(1245000)).toBe("₹12,450");
    expect(formatInr(123456789)).toBe("₹12,34,567.89");
    expect(formatInr(1000000000)).toBe("₹1,00,00,000");
  });

  it("handles zero and negatives", () => {
    expect(formatInr(0)).toBe("₹0");
    expect(formatInr(-30000)).toBe("-₹300");
  });

  it("rejects non-integer paise, which would signal float money upstream", () => {
    expect(() => formatInr(300.5)).toThrow();
  });
});

describe("rupeesToPaise", () => {
  it.each([
    ["350", 35000],
    ["349.5", 34950],
    ["349.50", 34950],
    ["0.05", 5],
    [" ₹ 1200 ", 120000],
    ["1234567.89", 123456789],
  ])("%j -> %i paise, digit-exact", (input, paise) => {
    expect(rupeesToPaise(input)).toBe(paise);
  });

  it("never rounds through a float", () => {
    // 0.29 * 100 is 28.999999999999996 in floating point.
    expect(rupeesToPaise("0.29")).toBe(29);
    expect(rupeesToPaise("19.99")).toBe(1999);
  });

  it.each(["", "abc", "12.345", "-5", "1,200", "12.", ".5", "12345678"])(
    "rejects %j",
    (input) => {
      expect(rupeesToPaise(input)).toBeNull();
    },
  );
});
