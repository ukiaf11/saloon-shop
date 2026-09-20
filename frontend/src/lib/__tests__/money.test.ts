import { describe, expect, it } from "vitest";

import { formatInr } from "../money";

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
