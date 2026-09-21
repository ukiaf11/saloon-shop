"use client";

import { useId, useState } from "react";

import { changePassword, errorMessage, SessionEnded } from "@/lib/owner-api";
import type { OwnerUser } from "@/types/owner";

import { Field, inputClass, Notice } from "./ui";

export function AccountPanel({
  token,
  user,
  onSessionEnded,
  onSignOut,
}: {
  token: string;
  user: OwnerUser;
  onSessionEnded: () => void;
  onSignOut: () => void;
}) {
  const ids = { current: useId(), next: useId(), repeat: useId() };
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setDone(false);
    if (next !== repeat) {
      setError("The two new passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      await changePassword(token, current, next);
      setCurrent("");
      setNext("");
      setRepeat("");
      setDone(true);
    } catch (err) {
      if (err instanceof SessionEnded) return onSessionEnded();
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="clay p-5 sm:p-6">
        <p className="text-ink font-bold">{user.full_name || user.email}</p>
        <p className="text-ink-soft text-sm">{user.email}</p>
        {!user.mfa_enabled ? (
          <p className="text-ink-muted mt-3 text-sm">
            Two-step sign-in is not set up yet. Until it is, use a long password that you
            use nowhere else.
          </p>
        ) : null}
        <button
          type="button"
          onClick={onSignOut}
          className="clay-btn-soft mt-4 px-6 py-3 text-sm font-bold"
        >
          Sign out
        </button>
      </div>

      <form onSubmit={submit} className="clay space-y-4 p-5 sm:p-6" noValidate>
        <h3 className="font-display text-ink text-xl">Change password</h3>
        <Field id={ids.current} label="Current password">
          <input
            id={ids.current}
            type="password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            autoComplete="current-password"
            className={inputClass}
          />
        </Field>
        <Field
          id={ids.next}
          label="New password"
          hint="At least 12 characters. Other devices signed in to this account are signed out."
        >
          <input
            id={ids.next}
            type="password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            autoComplete="new-password"
            className={inputClass}
          />
        </Field>
        <Field id={ids.repeat} label="New password again">
          <input
            id={ids.repeat}
            type="password"
            value={repeat}
            onChange={(e) => setRepeat(e.target.value)}
            autoComplete="new-password"
            className={inputClass}
          />
        </Field>
        {error ? <Notice tone="error">{error}</Notice> : null}
        {done ? <Notice tone="success">Password changed.</Notice> : null}
        <button
          type="submit"
          disabled={busy}
          className="clay-btn w-full px-6 py-3 text-sm font-bold"
        >
          {busy ? "Saving…" : "Change password"}
        </button>
      </form>
    </div>
  );
}
