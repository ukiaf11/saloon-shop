/**
 * Server-side readers for the public marketing content.
 *
 * Called from React Server Components only. Every function returns already
 * validated data (or a safe empty value) so a section component never has to
 * think about transport, parsing or failure.
 *
 * ## On caching
 *
 * These endpoints change rarely but must not be stale after an owner edits a
 * price or an opening hour, so each read carries a `revalidate` window and a
 * cache tag. The window is the backstop; the tag is the real mechanism -- the
 * admin save path calls `revalidateTag(CACHE_TAGS.services)` and the change is
 * live on the next request.
 *
 * Without the tag, Next caches these responses persistently and an owner's
 * price edit would never reach the page until the next deploy. That is not
 * theoretical: it was observed during Phase 2 development, where a rebuild kept
 * serving a stale payload until the fetch cache was deleted by hand.
 *
 * Reads pass `credentials: "omit"`. These endpoints are unauthenticated, and
 * sending cookies to them both leaks the admin session to a public route and
 * narrows what Next is willing to cache.
 *
 * ## On failure handling
 *
 * Every reader degrades instead of throwing. If the API is down, the marketing
 * page still renders -- the salon's phone number, address and directions are
 * baked into the page and are worth more to a visitor than a live services
 * grid. A thrown error here would blank the whole page and lose them.
 *
 * THIS APPLIES ONLY TO THESE READ-ONLY MARKETING READERS. Do not copy the
 * pattern into quote, order, payment, coupon or admin code: there, swallowing a
 * failure and continuing with an empty value would let the user act on data
 * that does not exist -- a silently wrong price or a checkout that looks like
 * it worked. Those paths must fail loudly.
 */

import type { z } from "zod";

import { ApiError, apiRequest } from "@/lib/api";
import {
  faqListSchema,
  gallerySchema,
  legalPageSchema,
  salonSchema,
  serviceListSchema,
  testimonialListSchema,
  type Faq,
  type GalleryImage,
  type LegalPage,
  type LegalPageSlug,
  type Salon,
  type ServiceList,
  type Testimonial,
} from "@/types/api";

/**
 * Tag names for on-demand revalidation, mirroring the backend cache keys in
 * API_CONTRACT_PHASE2.md. Declared here so the later wiring and the admin-side
 * `revalidateTag` calls share one spelling instead of two string literals.
 */
export const CACHE_TAGS = {
  salon: "salon",
  services: "services",
  gallery: "gallery",
  testimonials: "testimonials",
  faqs: "faqs",
  legal: "legal",
} as const;

/** Keep log lines flat: an ApiError's code is what anyone debugging needs. */
function describeFailure(error: unknown): string {
  if (error instanceof ApiError) {
    return `${error.code} (HTTP ${error.status})`;
  }
  return error instanceof Error ? error.message : String(error);
}

/** Backstop window. On-demand `revalidateTag` is the primary mechanism. */
const REVALIDATE_SECONDS = 300;

async function readPublic<T>(
  path: string,
  schema: z.ZodType<T>,
  tag: string,
): Promise<T | null> {
  try {
    return await apiRequest(path, schema, {
      credentials: "omit",
      next: { revalidate: REVALIDATE_SECONDS, tags: [tag] },
    });
  } catch (error) {
    // Loud on purpose: a build that runs while the API is down still exits 0
    // and ships a page of empty sections. This line is the only signal.
    console.error(`[site-data] ${path} unavailable: ${describeFailure(error)}`);
    return null;
  }
}

/** Salon profile, business hours and CMS content. Null when unreachable. */
export async function getSalon(): Promise<Salon | null> {
  return readPublic("/salon", salonSchema, CACHE_TAGS.salon);
}

/**
 * Active services plus their categories. Falls back to an empty catalogue so
 * the services section can render its own "unavailable" state rather than
 * taking the page down with it.
 */
export async function getServices(): Promise<ServiceList> {
  return (
    (await readPublic("/services", serviceListSchema, CACHE_TAGS.services)) ?? {
      categories: [],
      results: [],
    }
  );
}

export async function getGallery(): Promise<GalleryImage[]> {
  return (await readPublic("/gallery", gallerySchema, CACHE_TAGS.gallery))?.results ?? [];
}

export async function getTestimonials(): Promise<Testimonial[]> {
  return (
    (await readPublic("/testimonials", testimonialListSchema, CACHE_TAGS.testimonials))
      ?.results ?? []
  );
}

export async function getFaqs(): Promise<Faq[]> {
  return (await readPublic("/faqs", faqListSchema, CACHE_TAGS.faqs))?.results ?? [];
}

/**
 * A legal page by slug, or null when it has no published version.
 *
 * An unpublished page is a normal state, not an outage, so a 404 is not logged
 * as an error -- otherwise the logs fill with noise before the owner has
 * written the refund policy. The caller decides between notFound() and a
 * placeholder.
 */
export async function getLegalPage(slug: LegalPageSlug): Promise<LegalPage | null> {
  try {
    return await apiRequest(`/legal/${slug}`, legalPageSchema, {
      credentials: "omit",
      next: { revalidate: REVALIDATE_SECONDS, tags: [CACHE_TAGS.legal, `legal:${slug}`] },
    });
  } catch (error) {
    if (error instanceof ApiError && error.code === "not_found") {
      return null;
    }
    console.error(`[site-data] /legal/${slug} unavailable: ${describeFailure(error)}`);
    return null;
  }
}
