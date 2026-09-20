/**
 * The weekly opening table. Server component.
 *
 * Deliberately static: nothing here is highlighted as "open now". Comparing the
 * current time against the salon's timezone would render differently on the
 * server than in the visitor's browser and produce a hydration mismatch, and a
 * cached or prerendered page would go on claiming "Open now" hours later. A
 * live open/closed badge needs a client component that computes the state after
 * mount, in the salon's timezone -- not this table.
 */

import type { BusinessHour } from "@/types/api";

import { Section } from "./section";

/**
 * "21:00" -> "9:00 PM". Plain string arithmetic on purpose: Date and
 * Intl.DateTimeFormat would drag in the runtime's timezone and locale, which is
 * exactly the server/client divergence this section avoids.
 */
function to12Hour(time: string): string {
  const [rawHour, rawMinute] = time.split(":");
  const hour = Number(rawHour);
  if (!Number.isInteger(hour) || rawMinute === undefined) return time;
  const suffix = hour < 12 ? "AM" : "PM";
  const hour12 = hour % 12 === 0 ? 12 : hour % 12;
  return `${hour12}:${rawMinute} ${suffix}`;
}

function describeHours(hour: BusinessHour): string {
  // A missing time is treated as closed whatever the flag says -- better an
  // honest "Closed" than "10:00 AM – null".
  if (hour.is_closed || !hour.open_time || !hour.close_time) return "Closed";
  return `${to12Hour(hour.open_time)} – ${to12Hour(hour.close_time)}`;
}

export function OpeningHoursSection({ hours }: { hours: BusinessHour[] }) {
  if (hours.length === 0) return null;

  // The contract guarantees Monday(0) -> Sunday(6); the sort is a cheap guard
  // so a reordered payload cannot print the week out of order.
  const week = [...hours].sort((a, b) => a.day_of_week - b.day_of_week);

  return (
    <Section id="hours" title="Opening hours">
      <dl className="border-ink-700/60 bg-ink-900 rounded-card max-w-md border">
        {week.map((hour) => {
          const closed = hour.is_closed || !hour.open_time || !hour.close_time;
          return (
            <div
              key={hour.day_of_week}
              className="border-ink-800 flex items-baseline justify-between gap-4 border-b px-5 py-3 last:border-b-0"
            >
              <dt className="text-ivory-300 text-sm">{hour.day_name}</dt>
              {/* Closed days are marked by the word, not only by colour. */}
              <dd
                className={
                  closed ? "text-ivory-500 text-sm" : "text-ivory-50 text-sm tabular-nums"
                }
              >
                {describeHours(hour)}
              </dd>
            </div>
          );
        })}
      </dl>
    </Section>
  );
}
