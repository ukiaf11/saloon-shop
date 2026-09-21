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
    <div>
      <p className="text-gold-400 font-[family-name:var(--font-display-loaded)] text-4xl">
        <Counter value={value} />
        {of !== undefined ? (
          <span className="text-ivory-500 text-2xl"> / {of}</span>
        ) : null}
      </p>
      <p className="text-ivory-300 mt-1 text-sm">{label}</p>
    </div>
  );
}

export function CampaignSection() {
  const [data, setData] = useState<PromotionToday | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
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

  return (
    <Section id="campaign" title="Today's lucky offer">
      {loaded && data ? (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
        >
          <div className="border-ink-700/60 bg-ink-900 rounded-card grid gap-8 border p-6 sm:grid-cols-3 sm:p-8">
            <Stat value={data.paid_count} of={data.capacity} label="Slots filled" />
            <Stat
              value={data.winners_found}
              of={data.lucky_count}
              label="Lucky winners found"
            />
            <Stat value={data.slots_remaining} label="Slots remaining" />
          </div>

          <p className="text-ivory-500 mt-4 text-sm" aria-live="polite">
            {data.is_open ? (
              <>
                {data.winners_remaining} lucky{" "}
                {data.winners_remaining === 1 ? "slot" : "slots"} still unclaimed today.
                Pick {data.min_distinct_services} or more services to save{" "}
                {data.discount_percent}%.
              </>
            ) : (
              // Said plainly rather than hidden: someone who cannot enter today
              // should be told, not left to discover it at checkout.
              <>Today&apos;s promotion is full. Booking reopens tomorrow.</>
            )}
          </p>
        </motion.div>
      ) : (
        <div className="border-ink-700/60 bg-ink-900 rounded-card border p-6 sm:p-8">
          <p className="text-ivory-300 text-sm">
            {loaded
              ? // Data unavailable. The offer is still true; only the live
                // counts are missing, so say that instead of showing zeros
                // that would read as "nobody has booked".
                "Live slot counts are unavailable right now. The daily lucky offer still applies — pick your services to continue."
              : "Loading today's offer…"}
          </p>
        </div>
      )}

      <p className="text-ivory-500 mt-4 text-xs">
        Daily promotional capacity and campaign rules apply.{" "}
        <a href="/promotion-rules" className="hover:text-gold-400 underline">
          View promotion rules
        </a>
      </p>
    </Section>
  );
}
