import type { Testimonial } from "@/types/api";

import { Section } from "./section";

const MAX_RATING = 5;
const STAR_POSITIONS = [1, 2, 3, 4, 5];

function Rating({ rating }: { rating: number }) {
  return (
    <p className="flex items-center gap-1">
      {/* The stars are decoration; this is the rating for a screen reader. */}
      <span className="sr-only">
        Rated {rating} out of {MAX_RATING}
      </span>
      {STAR_POSITIONS.map((position) => (
        <svg
          key={position}
          aria-hidden="true"
          width="18"
          height="18"
          viewBox="0 0 20 20"
          className={position <= rating ? "fill-lucky" : "fill-clay-deep"}
        >
          <path d="M10 1.6l2.5 5.2 5.7.8-4.1 4 1 5.7-5.1-2.7-5.1 2.7 1-5.7-4.1-4 5.7-.8L10 1.6z" />
        </svg>
      ))}
    </p>
  );
}

/**
 * Renders nothing until real reviews exist. Invented testimonials on a real
 * business's site misrepresent what customers think, so an empty section is
 * the honest state -- and the one the seed data leaves it in.
 */
export function TestimonialsSection({ testimonials }: { testimonials: Testimonial[] }) {
  if (testimonials.length === 0) return null;

  return (
    <Section id="reviews" eyebrow="Reviews" title="What our customers say" align="center">
      <ul className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {testimonials.map((testimonial) => (
          <li key={testimonial.id}>
            <figure className="clay flex h-full flex-col p-6">
              <Rating rating={testimonial.rating} />
              <blockquote className="mt-4 flex-1">
                <p className="text-ink leading-relaxed">“{testimonial.body}”</p>
              </blockquote>
              <figcaption className="text-ink-soft mt-5 flex items-center gap-3 text-sm font-bold">
                <span
                  aria-hidden="true"
                  className="bg-peach text-ink flex h-10 w-10 items-center justify-center rounded-full font-extrabold"
                >
                  {testimonial.author_name.charAt(0)}
                </span>
                {testimonial.author_name}
              </figcaption>
            </figure>
          </li>
        ))}
      </ul>
    </Section>
  );
}
