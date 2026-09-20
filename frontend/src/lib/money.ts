/**
 * Display-only money helpers.
 *
 * The backend is the sole authority on every amount (REQUIREMENTS.md 4.6).
 * Nothing here computes a price, a discount or a total -- these functions only
 * render paise that the server already decided. Keep it that way: any
 * arithmetic added here becomes a second source of truth.
 */

/** Indian digit grouping: 1234567 -> "12,34,567". */
function groupIndian(n: number): string {
  const s = String(n);
  if (s.length <= 3) return s;
  const head = s.slice(0, -3);
  const tail = s.slice(-3);
  const parts: string[] = [];
  let rest = head;
  while (rest.length > 2) {
    parts.unshift(rest.slice(-2));
    rest = rest.slice(0, -2);
  }
  if (rest) parts.unshift(rest);
  return `${parts.join(",")},${tail}`;
}

/** Render paise as INR. Mirrors common.money.format_inr on the backend. */
export function formatInr(paise: number): string {
  if (!Number.isInteger(paise)) {
    throw new Error(`formatInr expects integer paise, got ${paise}`);
  }
  if (paise < 0) return `-${formatInr(-paise)}`;
  const rupees = Math.floor(paise / 100);
  const remainder = paise % 100;
  const grouped = groupIndian(rupees);
  return remainder === 0
    ? `₹${grouped}`
    : `₹${grouped}.${String(remainder).padStart(2, "0")}`;
}
