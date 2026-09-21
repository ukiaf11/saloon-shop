/**
 * UPI helpers for the QR payment fallback. Pure functions, so they are tested
 * directly rather than through the checkout.
 */

/** Paise to the "405.00" form UPI's `am` parameter expects. Integer maths only. */
export function paiseToUpiAmount(paise: number): string {
  if (!Number.isInteger(paise) || paise < 0) {
    throw new RangeError(`Invalid amount in paise: ${paise}`);
  }
  const rupees = Math.floor(paise / 100);
  const rest = String(paise % 100).padStart(2, "0");
  return `${rupees}.${rest}`;
}

/**
 * A `upi://pay` link that opens the customer's UPI app with the payee, amount
 * and note filled in -- on a phone, the only way to pay a QR shown on that
 * same phone's screen without a second device.
 *
 * Each value is percent-encoded individually: URLSearchParams would turn
 * spaces into "+", which some UPI apps show literally in the payee name.
 */
export function upiPayLink({
  upiId,
  payeeName,
  amountPaise,
  note,
}: {
  upiId: string;
  payeeName?: string | null;
  amountPaise: number;
  note?: string;
}): string {
  const params: [string, string][] = [["pa", upiId]];
  if (payeeName) params.push(["pn", payeeName]);
  params.push(["am", paiseToUpiAmount(amountPaise)], ["cu", "INR"]);
  if (note) params.push(["tn", note]);
  return `upi://pay?${params.map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join("&")}`;
}

/** Strip the spaces and dashes people type when copying a UTR. */
export function normaliseUtr(raw: string): string {
  return raw.replace(/[\s-]/g, "");
}

/** A UPI transaction reference (UTR / RRN) is exactly 12 digits. */
export function isValidUtr(raw: string): boolean {
  return /^\d{12}$/.test(normaliseUtr(raw));
}

/** "123456789012" -> "1234 5678 9012", for reading against a banking app. */
export function formatUtr(utr: string): string {
  return utr.replace(/(\d{4})(?=\d)/g, "$1 ");
}
