"use client";

/**
 * The salon's UPI QR: the fallback way to take payment while no payment
 * gateway is configured. Changing it changes where every customer's money
 * goes, so saving asks for the owner's password again.
 */

import { useEffect, useId, useMemo, useState } from "react";

import { qrImageUrl } from "@/lib/payments";
import {
  errorMessage,
  getPaymentSettings,
  savePaymentSettings,
  SessionEnded,
} from "@/lib/owner-api";
import type { PaymentSettings } from "@/types/owner";

import { Field, inputClass, Notice, whenText } from "./ui";

// The server's limit, which sits under Vercel's 4.5 MB request cap.
const MAX_BYTES = 4 * 1024 * 1024;

export function QrSettingsPanel({
  token,
  onSessionEnded,
}: {
  token: string;
  onSessionEnded: () => void;
}) {
  const ids = {
    file: useId(),
    upi: useId(),
    name: useId(),
    password: useId(),
  };
  const [settings, setSettings] = useState<PaymentSettings | null>(null);
  const [file, setFile] = useState<File | null>(null);
  // Remounts the file input after a save, so it stops naming a file that has
  // already been uploaded.
  const [fileInputKey, setFileInputKey] = useState(0);
  const [upiId, setUpiId] = useState("");
  const [payeeName, setPayeeName] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getPaymentSettings(token)
      .then((current) => {
        if (cancelled) return;
        setSettings(current);
        setUpiId(current.upi_id);
        setPayeeName(current.payee_name);
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

  // A local preview of the picked file, released when it is replaced or the
  // panel closes.
  const preview = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
  useEffect(
    () => () => {
      if (preview) URL.revokeObjectURL(preview);
    },
    [preview],
  );

  const save = async (removeQr: boolean) => {
    setError(null);
    setSaved(null);
    if (!password) {
      setError("Enter your password to save changes to the payment QR.");
      return;
    }
    if (file && file.size > MAX_BYTES) {
      setError("That image is larger than 4 MB. Take a screenshot of the QR instead.");
      return;
    }
    const form = new FormData();
    form.set("password", password);
    form.set("upi_id", upiId.trim());
    form.set("payee_name", payeeName.trim());
    if (removeQr) form.set("remove_qr", "true");
    else if (file) form.set("qr_image", file);

    setBusy(true);
    try {
      const next = await savePaymentSettings(token, form);
      setSettings(next);
      setFile(null);
      setFileInputKey((n) => n + 1);
      setPassword("");
      setSaved(
        removeQr
          ? "QR removed. Customers can no longer pay online until you add one again."
          : "Saved. Customers see this at checkout straight away.",
      );
    } catch (err) {
      if (err instanceof SessionEnded) return onSessionEnded();
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  if (!settings) {
    return error ? (
      <Notice tone="error">{error}</Notice>
    ) : (
      <p className="text-ink-soft">Loading payment settings…</p>
    );
  }

  const live = settings.method === "upi_qr";
  const shown = preview ?? (settings.qr ? qrImageUrl(settings.qr.version) : null);

  return (
    <div className="space-y-5">
      {settings.gateway_configured ? (
        <Notice tone="info">
          Online payments are set up, so customers pay through the payment gateway and
          this QR is not shown.
        </Notice>
      ) : live ? (
        <Notice tone="success">
          Customers are paying with this QR. Check each payment in your UPI app, then
          confirm it under “To confirm”.
        </Notice>
      ) : (
        <Notice tone="warning">
          No QR yet, so customers cannot pay online. Upload your UPI QR to start taking
          payments. When online payments are set up later, the QR switches off by itself.
        </Notice>
      )}

      <div className="clay p-5 sm:p-6">
        <div className="grid items-start gap-6 sm:grid-cols-[14rem_1fr]">
          <figure className="clay-well mx-auto flex w-full max-w-[16rem] flex-col items-center p-3">
            {shown ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={shown}
                alt={preview ? "The new QR you picked" : "Your current payment QR"}
                width={220}
                height={220}
                className="aspect-square w-full rounded-xl bg-white object-contain p-1"
              />
            ) : (
              <div className="text-ink-muted flex aspect-square w-full items-center justify-center text-center text-sm">
                No QR uploaded
              </div>
            )}
            <figcaption className="text-ink-muted mt-2 text-center text-xs">
              {preview
                ? "New — not saved yet"
                : settings.qr?.updated_at
                  ? `Updated ${whenText(settings.qr.updated_at)}`
                  : ""}
            </figcaption>
          </figure>

          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              void save(false);
            }}
            noValidate
          >
            <Field
              id={ids.file}
              label={settings.qr ? "Replace QR image" : "QR image"}
              hint="A clear screenshot or photo of your UPI QR (PNG, JPEG or WebP, up to 4 MB)."
            >
              <input
                key={fileInputKey}
                id={ids.file}
                type="file"
                accept="image/png,image/jpeg,image/webp"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="text-ink-soft file:clay-btn-soft file:text-ink block w-full text-sm file:mr-3 file:border-0 file:px-4 file:py-2 file:font-bold"
              />
            </Field>

            <Field
              id={ids.upi}
              label="UPI ID (optional)"
              hint="Lets customers on a phone tap to open their UPI app with the amount filled in. Works best with a business UPI ID."
            >
              <input
                id={ids.upi}
                value={upiId}
                onChange={(e) => setUpiId(e.target.value)}
                autoComplete="off"
                autoCapitalize="none"
                spellCheck={false}
                placeholder="yourname@okaxis"
                className={inputClass}
              />
            </Field>

            <Field id={ids.name} label="Name shown to customers (optional)">
              <input
                id={ids.name}
                value={payeeName}
                onChange={(e) => setPayeeName(e.target.value)}
                maxLength={100}
                placeholder="Upendra Salon"
                className={inputClass}
              />
            </Field>

            <Field
              id={ids.password}
              label="Your password"
              hint="Needed for every change here, because it decides where customers' money goes."
            >
              <input
                id={ids.password}
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                className={inputClass}
              />
            </Field>

            {error ? <Notice tone="error">{error}</Notice> : null}
            {saved ? <Notice tone="success">{saved}</Notice> : null}

            <div className="flex flex-col gap-3 sm:flex-row">
              <button
                type="submit"
                disabled={busy}
                className="clay-btn flex-[2] px-6 py-3 text-sm font-bold"
              >
                {busy ? "Saving…" : "Save"}
              </button>
              {settings.qr ? (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void save(true)}
                  className="clay-btn-soft text-danger flex-1 px-6 py-3 text-sm font-bold"
                >
                  Remove QR
                </button>
              ) : null}
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
