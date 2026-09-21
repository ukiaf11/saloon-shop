"use client";

/**
 * Today's campaign progress.
 *
 * Doc 3 section 6 is emphatic on two points and both are honoured here:
 * counters animate only *after* real data has arrived, and progress is never
 * faked. If the API is unreachable the section shows the offer without numbers
 * rather than inventing any — a fabricated "3 of 5 winners found" would be a
 * lie told to create urgency.
 *
 * Client-side because it polls: these counters change with every payment, and
 * a customer deciding whether to book needs the live figure, not one baked in
 * at build time.
 */

import { motion, useReducedMotion } from "motion/react";
import { useEffect, useState } from "react";

import { StarArt } from "@/components/clay/clay-art";
import { BOOKING_ENABLED } from "@/lib/api";
import { getPromotionToday } from "@/lib/site-data";
import type { PromotionToday } from "@/types/api";

import { Section } from "./section";

const POLL_MS = 30_000;

/** Counts up to `value` once the data is in. Never animates from a guess. */
function Counter({ value, duration = 900 }: { value: number; duration?: number }) {
  const reduceMotion = useReducedMotion();
  const [animated, setAnimated] = useState(0);

  useEffect(() => {
    // Nothing to animate, and nothing to set: the reduced-motion case is
    // derived at render time instead, so no state is written here.
    if (reduceMotion) return;

    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      // Ease-out: fast then settling, which reads as a counter landing rather
      // than a number scrolling.
      setAnimated(Math.round(value * (1 - Math.pow(1 - progress, 3))));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value, duration, reduceMotion]);

  return <span className="tabular-nums">{reduceMotion ? value : animated}</span>;
}

function Stat({ value, of, label }: { value: number; of?: number; label: string }) {
  return (
    <div className="clay-sm px-5 py-4">
      <p className="font-display text-ink text-4xl">
        <Counter value={value} />
        {of !== undefined ? (
          <span className="text-ink-muted text-2xl"> / {of}</span>
        ) : null}
      </p>
      <p className="text-ink-soft mt-1 text-sm font-semibold">{label}</p>
    </div>
  );
}

/**
 * One star per lucky slot: filled once that slot has been won. Counts come
 * straight from the API -- this shows how many were found, never which
 * positions, which the server does not reveal.
 */
function LuckyStars({ found, total }: { found: number; total: number }) {
  return (
    <ul
      className="flex flex-wrap gap-2"
      aria-label={`${found} of ${total} lucky slots found`}
    >
      {Array.from({ length: total }, (_, i) => {
        const won = i < found;
        return (
          <li
            key={i}
            className={`flex h-12 w-12 items-center justify-center rounded-2xl sm:h-14 sm:w-14 ${
              won ? "bg-lucky-soft" : "clay-well"
            }`}
          >
            <span className={won ? "" : "opacity-30 grayscale"}>
              <StarArt size={32} />
            </span>
          </li>
        );
      })}
    </ul>
  );
}

export function CampaignSection() {
  const [data, setData] = useState<PromotionToday | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    // No public API on a static preview: do not poll an address that cannot
    // answer. The section still explains the offer; it just shows no counts.
    if (!BOOKING_ENABLED) return;

    let cancelled = false;

    const load = async () => {
      const next = await getPromotionToday();
      if (cancelled) return;
      setData(next);
      setLoaded(true);
    };

    void load();
    const timer = setInterval(() => void load(), POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  const filledPercent =
    data && data.capacity > 0 ? Math.round((data.paid_count / data.capacity) * 100) : 0;

  return (
    <Section
      id="campaign"
      eyebrow="Today's lucky offer"
      title="Five lucky slots, every single day"
      description="Each day's winning positions are fixed before anyone books. If your paid booking lands on one, your hair cut, shave and face massage are free."
    >
      <div className="clay p-6 sm:p-9">
        {loaded && data ? (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35 }}
          >
            <div className="grid gap-8 lg:grid-cols-[1.3fr_1fr] lg:items-center">
              <div>
                <div className="flex items-baseline justify-between gap-4">
                  <p className="text-ink font-bold">Slots filled today</p>
                  <p className="text-ink-soft text-sm font-bold tabular-nums">
                    {data.paid_count} of {data.capacity}
                  </p>
                </div>
                {/* A pressed-in clay track with a raised fill. */}
                <div
                  className="clay-well mt-3 h-6 overflow-hidden p-1"
                  role="progressbar"
                  aria-label="Promotional slots filled today"
                  aria-valuemin={0}
                  aria-valuemax={data.capacity}
                  aria-valuenow={data.paid_count}
                >
                  <motion.div
                    className="bg-primary h-full rounded-full shadow-[inset_2px_2px_4px_rgb(255_255_255/0.3)]"
                    initial={{ width: 0 }}
                    animate={{ width: `${filledPercent}%` }}
                    transition={{ duration: 0.9, ease: "easeOut" }}
                  />
                </div>

                <p className="text-ink mt-8 font-bold">Lucky slots won</p>
                <div className="mt-3">
                  <LuckyStars found={data.winners_found} total={data.lucky_count} />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 lg:grid-cols-1">
                <Stat value={data.slots_remaining} label="Slots left today" />
                <Stat value={data.winners_remaining} label="Lucky slots still open" />
              </div>
            </div>

            <p
              className={`mt-8 rounded-2xl px-5 py-4 text-sm font-semibold ${
                data.is_open ? "bg-mint text-ink" : "bg-rose text-ink"
              }`}
              aria-live="polite"
            >
              {data.is_open ? (
                <>
                  Pick {data.min_distinct_services} or more services to save{" "}
                  {data.discount_percent}% — and every paid booking takes the next slot.
                </>
              ) : (
                // Said plainly rather than hidden: someone who cannot enter today
                // should be told, not left to discover it at checkout.
                <>Today&apos;s promotion is full. Booking reopens tomorrow.</>
              )}
            </p>
          </motion.div>
        ) : (
          <div className="flex items-center gap-5">
            <div className="clay-well flex h-20 w-20 shrink-0 items-center justify-center">
              <StarArt size={52} />
            </div>
            <p className="text-ink-soft">
              {!BOOKING_ENABLED
                ? "Live slot counts appear here once online booking opens. The lucky draw runs on paid online bookings."
                : loaded
                  ? // Data unavailable. The offer is still true; only the live
                    // counts are missing, so say that instead of showing zeros
                    // that would read as "nobody has booked".
                    "Live slot counts are unavailable right now. The daily lucky offer still applies — pick your services to take part."
                  : "Loading today's offer…"}
            </p>
          </div>
        )}
      </div>

      <p className="text-ink-muted mt-5 text-sm">
        Daily promotional capacity and campaign rules apply.{" "}
        <a href="/promotion-rules" className="text-primary py-3 font-semibold underline">
          View promotion rules
        </a>
      </p>
    </Section>
  );
}
