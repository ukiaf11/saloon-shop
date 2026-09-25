"use client";

/**
 * Services & prices — the owner (or manager) sets their own prices here.
 *
 * The rules the backend enforces, reflected honestly in this UI:
 *  - every price change is written to a permanent price history, with who and
 *    why, so the panel asks for an optional reason and shows recent changes;
 *  - past orders keep their snapshotted prices — changing a price never
 *    rewrites what anyone already paid;
 *  - the public site updates within a few minutes; checkout always charges
 *    the live price.
 */

import { useEffect, useId, useState } from "react";

import { formatInr, rupeesToPaise } from "@/lib/money";
import {
  changeServicePrice,
  errorMessage,
  listOwnerServices,
  SessionEnded,
  updateOwnerService,
} from "@/lib/owner-api";
import type { OwnerService } from "@/types/owner";

import { inputClass, Notice, whenText } from "./ui";

export function ServicesPanel({
  token,
  onSessionEnded,
}: {
  token: string;
  onSessionEnded: () => void;
}) {
  const [services, setServices] = useState<OwnerService[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listOwnerServices(token)
      .then((rows) => {
        if (!cancelled) setServices(rows);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof SessionEnded) return onSessionEnded();
        setError(errorMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [token, onSessionEnded]);

  if (services === null) {
    return error ? (
      <Notice tone="error">{error}</Notice>
    ) : (
      <p className="text-ink-soft">Loading services…</p>
    );
  }

  const replace = (next: OwnerService) =>
    setServices((rows) => (rows ?? []).map((row) => (row.id === next.id ? next : row)));

  // Group by category, keeping the API's display order. Uncategorised last.
  const groups = new Map<string, OwnerService[]>();
  for (const service of services) {
    const key = service.category?.name ?? "More services";
    groups.set(key, [...(groups.get(key) ?? []), service]);
  }

  return (
    <div className="space-y-6">
      <Notice tone="info">
        Price changes go live on the website within a few minutes, and checkout always
        charges the current price. Bookings that were already placed keep the price the
        customer saw.
      </Notice>
      {services.length === 0 ? (
        <Notice tone="warning">
          No services yet. They are added when the catalogue is seeded.
        </Notice>
      ) : (
        [...groups.entries()].map(([category, rows]) => (
          <section key={category} aria-label={category}>
            <h3 className="font-display text-ink text-xl">{category}</h3>
            <div className="mt-3 space-y-4">
              {rows.map((service) => (
                <ServiceCard
                  key={service.id}
                  service={service}
                  token={token}
                  onChanged={replace}
                  onSessionEnded={onSessionEnded}
                />
              ))}
            </div>
          </section>
        ))
      )}
    </div>
  );
}

function ServiceCard({
  service,
  token,
  onChanged,
  onSessionEnded,
}: {
  service: OwnerService;
  token: string;
  onChanged: (next: OwnerService) => void;
  onSessionEnded: () => void;
}) {
  const ids = { price: useId(), reason: useId(), duration: useId() };
  const [editing, setEditing] = useState(false);
  const [price, setPrice] = useState("");
  const [reason, setReason] = useState("");
  const [duration, setDuration] = useState(String(service.duration_minutes));
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  const lastChange = service.price_history[0];

  const run = async (
    label: string,
    action: () => Promise<OwnerService>,
    done?: string,
  ) => {
    setBusy(label);
    setError(null);
    setSaved(null);
    try {
      const next = await action();
      onChanged(next);
      if (done) setSaved(done);
      return next;
    } catch (err) {
      if (err instanceof SessionEnded) {
        onSessionEnded();
        return null;
      }
      setError(errorMessage(err));
      return null;
    } finally {
      setBusy(null);
    }
  };

  const submitEdit = async (event: React.FormEvent) => {
    event.preventDefault();
    const newPaise = rupeesToPaise(price);
    if (newPaise === null || newPaise < 100) {
      setError("Enter the new price in rupees — at least ₹1, like 350 or 349.50.");
      return;
    }
    const minutes = Number(duration);
    if (!Number.isInteger(minutes) || minutes < 5 || minutes > 480) {
      setError("Duration must be between 5 and 480 minutes.");
      return;
    }

    setBusy("edit");
    setError(null);
    setSaved(null);
    try {
      let next = service;
      if (minutes !== service.duration_minutes) {
        next = await updateOwnerService(token, service.id, { duration_minutes: minutes });
      }
      if (newPaise !== service.price_paise) {
        next = await changeServicePrice(token, service.id, newPaise, reason.trim());
      } else if (minutes === service.duration_minutes) {
        setError("Nothing changed — the price and duration are already set to that.");
        setBusy(null);
        return;
      }
      onChanged(next);
      setEditing(false);
      setPrice("");
      setReason("");
      setSaved(
        newPaise !== service.price_paise
          ? `Price changed: ${formatInr(service.price_paise)} → ${formatInr(newPaise)}.`
          : "Duration updated.",
      );
    } catch (err) {
      if (err instanceof SessionEnded) return onSessionEnded();
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  return (
    <article className={`clay p-5 sm:p-6 ${service.is_active ? "" : "opacity-80"}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h4 className="font-display text-ink text-xl">{service.name}</h4>
          <p className="text-ink-muted mt-0.5 text-xs font-bold">
            {service.duration_minutes} min
            {lastChange
              ? ` · last price change ${
                  lastChange.changed_at ? whenText(lastChange.changed_at) : ""
                }: ${formatInr(lastChange.old_price_paise)} → ${formatInr(
                  lastChange.new_price_paise,
                )}`
              : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {service.is_featured ? (
            <span className="bg-lucky-soft text-ink rounded-full px-3 py-1 text-xs font-extrabold uppercase">
              Popular
            </span>
          ) : null}
          {!service.is_active ? (
            <span className="bg-rose text-danger rounded-full px-3 py-1 text-xs font-extrabold uppercase">
              Hidden
            </span>
          ) : null}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <p className="font-display text-ink text-3xl tabular-nums">
          {formatInr(service.price_paise)}
        </p>
        {!editing ? (
          <button
            type="button"
            onClick={() => {
              setEditing(true);
              setPrice(String(service.price_paise / 100));
              setDuration(String(service.duration_minutes));
              setSaved(null);
              setError(null);
            }}
            className="clay-btn min-h-11 px-5 text-sm font-bold"
          >
            Edit price
          </button>
        ) : null}
      </div>

      {editing ? (
        <form onSubmit={submitEdit} className="clay-well mt-4 space-y-3 p-4" noValidate>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label
                htmlFor={ids.price}
                className="text-ink mb-2 block text-sm font-bold"
              >
                New price (₹)
              </label>
              <input
                id={ids.price}
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                inputMode="decimal"
                autoComplete="off"
                placeholder="350"
                className={`${inputClass} tabular-nums`}
              />
            </div>
            <div>
              <label
                htmlFor={ids.duration}
                className="text-ink mb-2 block text-sm font-bold"
              >
                Duration (minutes)
              </label>
              <input
                id={ids.duration}
                value={duration}
                onChange={(e) => setDuration(e.target.value)}
                inputMode="numeric"
                autoComplete="off"
                className={`${inputClass} tabular-nums`}
              />
            </div>
          </div>
          <div>
            <label htmlFor={ids.reason} className="text-ink mb-2 block text-sm font-bold">
              Reason{" "}
              <span className="text-ink-muted font-semibold">
                (optional — kept in the price history)
              </span>
            </label>
            <input
              id={ids.reason}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              maxLength={200}
              placeholder="e.g. Festival pricing"
              className={inputClass}
            />
          </div>
          {error ? <Notice tone="error">{error}</Notice> : null}
          <div className="flex gap-3">
            <button
              type="button"
              disabled={busy !== null}
              onClick={() => {
                setEditing(false);
                setError(null);
              }}
              className="clay-btn-soft flex-1 px-4 py-3 text-sm font-bold"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={busy !== null}
              className="clay-btn flex-[2] px-4 py-3 text-sm font-bold"
            >
              {busy === "edit" ? "Saving…" : "Save new price"}
            </button>
          </div>
        </form>
      ) : null}

      {!editing && error ? (
        <div className="mt-3">
          <Notice tone="error">{error}</Notice>
        </div>
      ) : null}
      {saved ? (
        <div className="mt-3">
          <Notice tone="success">{saved}</Notice>
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy !== null}
          aria-pressed={service.is_featured}
          onClick={() =>
            void run("featured", () =>
              updateOwnerService(token, service.id, {
                is_featured: !service.is_featured,
              }),
            )
          }
          className={`min-h-11 px-4 text-xs font-bold ${
            service.is_featured ? "clay-btn" : "clay-btn-soft text-ink-soft"
          }`}
        >
          {busy === "featured"
            ? "…"
            : service.is_featured
              ? "★ Popular"
              : "☆ Mark popular"}
        </button>
        <button
          type="button"
          disabled={busy !== null}
          aria-pressed={service.is_active}
          onClick={() =>
            void run(
              "active",
              () =>
                updateOwnerService(token, service.id, { is_active: !service.is_active }),
              service.is_active
                ? `${service.name} is now hidden from the website.`
                : `${service.name} is back on the website.`,
            )
          }
          className={`min-h-11 px-4 text-xs font-bold ${
            service.is_active ? "clay-btn-soft text-ink-soft" : "clay-btn"
          }`}
        >
          {busy === "active"
            ? "…"
            : service.is_active
              ? "Hide from website"
              : "Show on website"}
        </button>
      </div>

      {service.price_history.length > 1 ? (
        <details className="mt-4">
          <summary className="text-primary cursor-pointer text-sm font-bold">
            Price history
          </summary>
          <ul className="text-ink-soft mt-2 space-y-1 text-sm">
            {service.price_history.map((entry, index) => (
              <li key={index} className="tabular-nums">
                {formatInr(entry.old_price_paise)} → {formatInr(entry.new_price_paise)}
                {entry.changed_at ? ` · ${whenText(entry.changed_at)}` : ""}
                {entry.changed_by ? ` · ${entry.changed_by}` : ""}
                {entry.reason ? ` · “${entry.reason}”` : ""}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </article>
  );
}
