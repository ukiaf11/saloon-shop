import { ClockArt } from "@/components/clay/clay-art";
import type { BusinessHour } from "@/types/api";

/** "10:00" -> "10:00 AM". Presentation only; the backend owns the times. */
function to12Hour(time: string): string {
  const [rawHour, rawMinute] = time.split(":");
  const hour = Number(rawHour);
  if (!Number.isInteger(hour) || rawMinute === undefined) return time;
  const suffix = hour < 12 ? "AM" : "PM";
  const hour12 = hour % 12 === 0 ? 12 : hour % 12;
  return `${hour12}:${rawMinute} ${suffix}`;
}

function describeHours(hour: BusinessHour): string {
  if (hour.is_closed || !hour.open_time || !hour.close_time) return "Closed";
  return `${to12Hour(hour.open_time)} – ${to12Hour(hour.close_time)}`;
}

/**
 * Rendered inside the contact block rather than as its own section, so the
 * hours sit beside the address -- the two things someone planning a visit
 * reads together.
 *
 * Deliberately does NOT highlight "today": server and client clocks can
 * disagree across midnight IST, which would cause a hydration mismatch.
 */
export function OpeningHoursCard({ hours }: { hours: BusinessHour[] }) {
  if (hours.length === 0) return null;

  const week = [...hours].sort((a, b) => a.day_of_week - b.day_of_week);

  return (
    <div id="hours" className="clay scroll-mt-28 p-6 sm:p-8">
      <div className="flex items-center gap-3">
        <div className="bg-sky flex h-12 w-12 items-center justify-center rounded-2xl">
          <ClockArt size={36} />
        </div>
        <h3 className="font-display text-ink text-2xl">Opening hours</h3>
      </div>
      <dl className="mt-5 space-y-1.5">
        {week.map((hour) => {
          const closed = hour.is_closed || !hour.open_time || !hour.close_time;
          return (
            <div
              key={hour.day_of_week}
              className="odd:bg-clay-deep/60 flex items-baseline justify-between gap-4 rounded-xl px-3 py-2"
            >
              <dt className="text-ink-soft text-sm font-bold">{hour.day_name}</dt>
              {/* Closed days are marked by the word, not only by colour. */}
              <dd
                className={
                  closed
                    ? "text-danger text-sm font-bold"
                    : "text-ink text-sm font-semibold tabular-nums"
                }
              >
                {describeHours(hour)}
              </dd>
            </div>
          );
        })}
      </dl>
    </div>
  );
}
