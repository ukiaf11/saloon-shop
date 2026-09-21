/**
 * Small building blocks shared by the owner panel's tabs.
 */

export const inputClass =
  "clay-well w-full px-4 py-3 text-ink font-semibold placeholder:text-ink-muted placeholder:font-normal";

export function Field({
  id,
  label,
  hint,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label htmlFor={id} className="text-ink mb-2 block text-sm font-bold">
        {label}
      </label>
      {children}
      {hint ? <p className="text-ink-muted mt-1.5 text-xs">{hint}</p> : null}
    </div>
  );
}

export function Notice({
  tone,
  children,
}: {
  tone: "error" | "success" | "warning" | "info";
  children: React.ReactNode;
}) {
  const styles = {
    error: "bg-rose text-danger",
    success: "bg-mint text-success",
    warning: "bg-butter text-warning",
    info: "bg-sky text-ink",
  }[tone];
  return (
    <p
      role={tone === "error" ? "alert" : "status"}
      className={`${styles} rounded-2xl px-4 py-3 text-sm font-semibold`}
    >
      {children}
    </p>
  );
}

/** "3 min ago" for recent times, a local date-time otherwise. */
export function whenText(iso: string, now: number = Date.now()): string {
  const then = new Date(iso).getTime();
  const minutes = Math.round((now - then) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  if (minutes < 24 * 60) {
    const hours = Math.floor(minutes / 60);
    return `${hours} hr ago`;
  }
  return new Date(iso).toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** Short owner-facing labels for why a booking has no draw number. */
export const SKIP_LABEL: Record<string, string> = {
  REPEAT_ENTRY: "Not in the draw: this phone already entered today",
  DAY_FULL: "Not in the draw: the day's slots were full",
  DAY_CLOSED: "Not in the draw: confirmed after the day closed",
  HOLD_EXPIRED: "Not in the draw: the hold expired",
  NOT_RUNNING: "No draw was running",
};
