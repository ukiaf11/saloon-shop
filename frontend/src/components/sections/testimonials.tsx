/**
 * Published customer testimonials. Server component.
 */

import type { Testimonial } from "@/types/api";

import { Section } from "./section";

const MAX_RATING = 5;
const STAR_POSITIONS = [1, 2, 3, 4, 5];

function Rating({ rating }: { rating: number }) {
  return (
    <p className="flex items-center gap-0.5">
      {/* The stars are decoration; this is the rating for a screen reader. */}
      <span className="sr-only">
        Rated {rating} out of {MAX_RATING}
      </span>
      {STAR_POSITIONS.map((position) => (
        <svg
          key={position}
          aria-hidden="true"
          width="14"
          height="14"
          viewBox="0 0 20 20"
          className={position <= rating ? "fill-gold-400" : "fill-ink-600"}
        >
          <path d="M10 1.6l2.5 5.2 5.7.8-4.1 4 1 5.7-5.1-2.7-5.1 2.7 1-5.7-4.1-4 5.7-.8L10 1.6z" />
        </svg>
      ))}
    </p>
  );
}

export function TestimonialsSection({ testimonials }: { testimonials: Testimonial[] }) {
  // Nothing published yet: render nothing rather than an empty compliment box.
  if (testimonials.length === 0) return null;

  return (
    <Section id="reviews" title="What our customers say">
      <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {testimonials.map((testimonial) => (
          <li key={testimonial.id}>
            <figure className="border-ink-700/60 bg-ink-900 rounded-card h-full border p-5">
              <Rating rating={testimonial.rating} />
              <blockquote className="mt-3">
                <p className="text-ivory-100 text-sm leading-relaxed">
                  {testimonial.body}
                </p>
              </blockquote>
              <figcaption className="text-ivory-500 mt-4 text-sm">
                {testimonial.author_name}
              </figcaption>
            </figure>
          </li>
        ))}
      </ul>
    </Section>
  );
}
