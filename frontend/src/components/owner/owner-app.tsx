"use client";

/**
 * The owner panel: sign in, then confirm UPI payments, send winners' refunds
 * and manage the payment QR.
 *
 * Everything shown comes from the API on each load; nothing about money is
 * kept or computed in the browser.
 */

import { useCallback, useEffect, useId, useState, useSyncExternalStore } from "react";

import {
  clearToken,
  errorMessage,
  getMe,
  listPayments,
  listRefunds,
  loadToken,
  saveToken,
  SessionEnded,
  signIn,
  signOut,
  subscribeToken,
  type PaymentListStatus,
} from "@/lib/owner-api";
import type { OwnerPayment, OwnerRefund, OwnerUser } from "@/types/owner";

import { AccountPanel } from "./account-panel";
import { PaymentCard } from "./payment-card";
import { QrSettingsPanel } from "./qr-settings";
import { RefundsPanel } from "./refunds-panel";
import { Field, inputClass, Notice } from "./ui";

type Session = { token: string; user: OwnerUser };
type Tab = "confirm" | "refunds" | "history" | "qr" | "account";

const REFRESH_MS = 30_000;

/** No token on the server: the panel only ever renders signed-in in a browser. */
const noToken = () => null;

export function OwnerApp() {
  const token = useSyncExternalStore(subscribeToken, loadToken, noToken);
  // The signed-in user, remembered against the token it was fetched for, so a
  // new token is never shown with a previous session's user.
  const [known, setKnown] = useState<Session | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!token || known?.token === token) return;
    let cancelled = false;
    getMe(token)
      .then(({ user }) => {
        if (!cancelled) setKnown({ token, user });
      })
      .catch(() => {
        // Expired or revoked while the tab was closed: back to sign-in.
        if (!cancelled) clearToken();
      });
    return () => {
      cancelled = true;
    };
  }, [token, known]);

  const onSessionEnded = useCallback(() => {
    clearToken();
    setKnown(null);
    setNotice("Your session has ended. Please sign in again.");
  }, []);

  if (!token) {
    return (
      <SignIn
        notice={notice}
        onSignedIn={(next) => {
          setKnown(next);
          setNotice(null);
          saveToken(next.token);
        }}
      />
    );
  }

  if (known?.token !== token) {
    return <p className="text-ink-soft py-16 text-center">Loading…</p>;
  }

  const session = known;
  const handleSignOut = () => {
    void signOut(session.token).catch(() => undefined);
    clearToken();
    setKnown(null);
    setNotice("You have signed out.");
  };

  if (session.user.role !== "OWNER") {
    return (
      <div className="clay mx-auto max-w-md p-6 text-center sm:p-8">
        <h1 className="font-display text-ink text-2xl">Owner only</h1>
        <p className="text-ink-soft mt-3">
          Payments are confirmed by the salon owner. This account can&apos;t use this page
          yet.
        </p>
        <button
          type="button"
          onClick={handleSignOut}
          className="clay-btn-soft mt-5 px-6 py-3 text-sm font-bold"
        >
          Sign out
        </button>
      </div>
    );
  }

  return (
    <Dashboard
      session={session}
      onSessionEnded={onSessionEnded}
      onSignOut={handleSignOut}
    />
  );
}

// --- sign in -----------------------------------------------------------------

function SignIn({
  notice,
  onSignedIn,
}: {
  notice: string | null;
  onSignedIn: (session: Session) => void;
}) {
  const ids = { email: useId(), password: useId() };
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const session = await signIn(email.trim(), password);
      onSignedIn({ token: session.token, user: session.user });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form
      onSubmit={submit}
      className="clay mx-auto max-w-md space-y-4 p-6 sm:p-8"
      noValidate
    >
      <h1 className="font-display text-ink text-3xl">Owner sign in</h1>
      {notice ? <Notice tone="info">{notice}</Notice> : null}
      <Field id={ids.email} label="Email">
        <input
          id={ids.email}
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          className={inputClass}
        />
      </Field>
      <Field id={ids.password} label="Password">
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
      <button
        type="submit"
        disabled={busy}
        className="clay-btn w-full px-6 py-3.5 font-bold"
      >
        {busy ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}

// --- dashboard ------------------------------------------------------------------

function Dashboard({
  session,
  onSessionEnded,
  onSignOut,
}: {
  session: Session;
  onSessionEnded: () => void;
  onSignOut: () => void;
}) {
  const { token, user } = session;
  const [tab, setTab] = useState<Tab>("confirm");
  const [awaiting, setAwaiting] = useState<OwnerPayment[] | null>(null);
  const [refunds, setRefunds] = useState<OwnerRefund[] | null>(null);
  const [recentlyDecided, setRecentlyDecided] = useState<OwnerPayment[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Bumping this reloads the queue and the refunds.
  const [reloads, setReloads] = useState(0);
  const refresh = useCallback(() => setReloads((n) => n + 1), []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([listPayments(token, "awaiting"), listRefunds(token, "pending")])
      .then(([nextAwaiting, nextRefunds]) => {
        if (cancelled) return;
        setAwaiting(nextAwaiting);
        setRefunds(nextRefunds);
        setError(null);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof SessionEnded) return onSessionEnded();
        setError(errorMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [token, reloads, onSessionEnded]);

  // New claims arrive while the owner has the page open; keep the queue fresh
  // without them having to reload, but only while they are looking at it.
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") refresh();
    }, REFRESH_MS);
    const onVisible = () => {
      if (document.visibilityState === "visible") refresh();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [refresh]);

  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: "confirm", label: "To confirm", count: awaiting?.length },
    { id: "refunds", label: "Refunds", count: refunds?.length },
    { id: "history", label: "History" },
    { id: "qr", label: "Payment QR" },
    { id: "account", label: "Account" },
  ];

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-ink-muted text-xs font-extrabold tracking-[0.12em] uppercase">
            Signed in as {user.full_name || user.email}
          </p>
          <h1 className="font-display text-ink mt-1 text-3xl sm:text-4xl">Payments</h1>
        </div>
        <button
          type="button"
          onClick={refresh}
          className="clay-btn-soft min-h-11 px-5 text-sm font-bold"
        >
          Refresh
        </button>
      </div>

      <div
        role="group"
        aria-label="Sections"
        className="-mx-4 mt-6 mb-6 flex [scrollbar-width:none] gap-3 overflow-x-auto px-4 pt-1 pb-3 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0 [&::-webkit-scrollbar]:hidden"
      >
        {tabs.map((item) => {
          const pressed = tab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              aria-pressed={pressed}
              onClick={() => setTab(item.id)}
              className={`min-h-11 shrink-0 px-5 text-sm font-bold whitespace-nowrap ${
                pressed ? "clay-btn" : "clay-btn-soft text-ink-soft"
              }`}
            >
              {item.label}
              {item.count ? (
                <span
                  className={`ml-2 rounded-full px-2 py-0.5 text-xs ${
                    pressed ? "text-primary bg-white" : "bg-lucky-soft text-ink"
                  }`}
                >
                  {item.count}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>

      {error ? (
        <div className="mb-5">
          <Notice tone="error">{error}</Notice>
        </div>
      ) : null}

      {tab === "confirm" ? (
        <div className="space-y-5">
          {recentlyDecided.map((payment) => (
            <DecidedBanner
              key={payment.id}
              payment={payment}
              onDismiss={() =>
                setRecentlyDecided((items) => items.filter((p) => p.id !== payment.id))
              }
              onOpenRefunds={() => setTab("refunds")}
            />
          ))}
          {awaiting === null ? (
            <p className="text-ink-soft">Loading payments…</p>
          ) : awaiting.length === 0 ? (
            <Notice tone="info">
              Nothing to confirm. When a customer pays with your QR and enters their UPI
              reference, it appears here.
            </Notice>
          ) : (
            awaiting.map((payment) => (
              <PaymentCard
                key={payment.id}
                payment={payment}
                token={token}
                onSessionEnded={onSessionEnded}
                onDecided={(decided) => {
                  setRecentlyDecided((items) => [decided, ...items].slice(0, 5));
                  refresh();
                }}
              />
            ))
          )}
        </div>
      ) : null}

      {tab === "refunds" ? (
        <RefundsPanel
          token={token}
          pending={refunds ?? []}
          onChanged={refresh}
          onSessionEnded={onSessionEnded}
        />
      ) : null}

      {tab === "history" ? (
        <History token={token} onSessionEnded={onSessionEnded} />
      ) : null}

      {tab === "qr" ? (
        <QrSettingsPanel token={token} onSessionEnded={onSessionEnded} />
      ) : null}

      {tab === "account" ? (
        <AccountPanel
          token={token}
          user={user}
          onSessionEnded={onSessionEnded}
          onSignOut={onSignOut}
        />
      ) : null}
    </div>
  );
}

function DecidedBanner({
  payment,
  onDismiss,
  onOpenRefunds,
}: {
  payment: OwnerPayment;
  onDismiss: () => void;
  onOpenRefunds: () => void;
}) {
  const won = payment.draw.status === "won";
  const refundDue = won && payment.draw.refund_paise > 0;
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="flex-1">
        <Notice tone={payment.status === "rejected" ? "warning" : "success"}>
          {payment.order.public_order_number}:{" "}
          {payment.status === "rejected"
            ? "marked as not received. The customer can send a new reference."
            : won
              ? `confirmed — draw #${payment.draw.participant_number} is a WINNER.`
              : "confirmed."}{" "}
          {refundDue ? (
            <button
              type="button"
              onClick={onOpenRefunds}
              className="underline underline-offset-4"
            >
              Send their refund
            </button>
          ) : null}
        </Notice>
      </div>
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss"
        className="clay-btn-soft text-ink-soft h-11 w-11 shrink-0 text-lg font-bold"
      >
        ×
      </button>
    </div>
  );
}

function History({
  token,
  onSessionEnded,
}: {
  token: string;
  onSessionEnded: () => void;
}) {
  const [status, setStatus] =
    useState<Exclude<PaymentListStatus, "awaiting">>("confirmed");
  // Keyed by the status it was loaded for; a result for the other status is
  // treated as still loading rather than shown under the wrong heading.
  const [loaded, setLoaded] = useState<{ status: string; items: OwnerPayment[] } | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const items = loaded?.status === status ? loaded.items : null;

  useEffect(() => {
    let cancelled = false;
    listPayments(token, status)
      .then((result) => {
        if (!cancelled) setLoaded({ status, items: result });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof SessionEnded) return onSessionEnded();
        setError(errorMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [token, status, onSessionEnded]);

  return (
    <div className="space-y-5">
      <div className="flex gap-2">
        {(["confirmed", "rejected"] as const).map((option) => (
          <button
            key={option}
            type="button"
            aria-pressed={status === option}
            onClick={() => setStatus(option)}
            className={`min-h-11 px-5 text-sm font-bold ${
              status === option ? "clay-btn" : "clay-btn-soft text-ink-soft"
            }`}
          >
            {option === "confirmed" ? "Received" : "Not received"}
          </button>
        ))}
      </div>
      {error ? <Notice tone="error">{error}</Notice> : null}
      {items === null ? (
        <p className="text-ink-soft">Loading…</p>
      ) : items.length === 0 ? (
        <Notice tone="info">Nothing here yet.</Notice>
      ) : (
        items.map((payment) => (
          <PaymentCard
            key={payment.id}
            payment={payment}
            token={token}
            onSessionEnded={onSessionEnded}
          />
        ))
      )}
    </div>
  );
}
