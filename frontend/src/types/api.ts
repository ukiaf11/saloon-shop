/**
 * Response schemas mirroring the backend serializers.
 *
 * Note what is absent and must stay absent: winning positions, campaign seeds,
 * gateway payment IDs, internal database IDs and any customer PII beyond what
 * the coupon holder already knows (REQUIREMENTS.md 3.4, 4.6).
 *
 * Shapes here track API_CONTRACT_PHASE2.md exactly. A drift on either side must
 * surface as a parse error at the boundary, not as an undefined in a component.
 */

import { z } from "zod";

export const readinessSchema = z.object({
  status: z.enum(["ok", "degraded"]),
  checks: z.record(z.string(), z.string()),
});
export type Readiness = z.infer<typeof readinessSchema>;

/**
 * GET /promotion/today -- the only campaign numbers safe to expose publicly.
 *
 * Note what is absent and must stay absent: the seed, its commitment, and the
 * winning positions. If a field resembling any of those ever appears here,
 * something upstream is leaking a result that has not happened yet.
 */
export const promotionTodaySchema = z.object({
  campaign_date: z.string(),
  capacity: z.number().int().nonnegative(),
  paid_count: z.number().int().nonnegative(),
  slots_remaining: z.number().int().nonnegative(),
  lucky_count: z.number().int().nonnegative(),
  winners_found: z.number().int().nonnegative(),
  winners_remaining: z.number().int().nonnegative(),
  discount_percent: z.number().int().min(0).max(100),
  min_distinct_services: z.number().int().positive(),
  is_open: z.boolean(),
  status: z.enum(["SCHEDULED", "ACTIVE", "CLOSED"]),
});
export type PromotionToday = z.infer<typeof promotionTodaySchema>;

/* -------------------------------------------------------------------------- */
/* GET /salon                                                                  */
/* -------------------------------------------------------------------------- */

/**
 * Times are "HH:MM" in the salon timezone; both are null when is_closed.
 * day_of_week is 0=Monday .. 6=Sunday -- not JS's Sunday-first convention.
 */
export const businessHourSchema = z.object({
  day_of_week: z.number().int().min(0).max(6),
  day_name: z.string(),
  open_time: z.string().nullable(),
  close_time: z.string().nullable(),
  is_closed: z.boolean(),
});
export type BusinessHour = z.infer<typeof businessHourSchema>;

export const whyChooseUsItemSchema = z.object({
  title: z.string(),
  body: z.string(),
});
export type WhyChooseUsItem = z.infer<typeof whyChooseUsItemSchema>;

/** Absent links are null, never "" -- the contract is explicit about this. */
/**
 * Tolerant by design. `social_links` is a free-form JSONB row the owner edits,
 * and the backend merges SiteContent over its defaults shallowly -- so saving
 * `{"instagram": "..."}` drops the `facebook` key entirely. With a strict
 * schema that single edit would fail the whole /salon parse and blank the
 * opening hours, contact panel and "why choose us" section along with it.
 * A missing or null link is simply an absent link.
 */
export const socialLinksSchema = z.object({
  instagram: z.string().nullish().default(null),
  facebook: z.string().nullish().default(null),
});
export type SocialLinks = z.infer<typeof socialLinksSchema>;

/**
 * Assembled server-side from SiteContent key/value rows. Every key is always
 * present -- the backend substitutes a documented default rather than omitting
 * it -- so nothing here is optional.
 */
export const salonContentSchema = z.object({
  hero_eyebrow: z.string(),
  hero_heading: z.string(),
  hero_subheading: z.string(),
  why_choose_us: z.array(whyChooseUsItemSchema),
  social_links: socialLinksSchema,
});
export type SalonContent = z.infer<typeof salonContentSchema>;

export const salonSchema = z.object({
  name: z.string(),
  slug: z.string(),
  timezone: z.string(),
  currency: z.literal("INR"),
  // All five contact fields are nullable: the backend normalises an unset
  // blank CharField to null so "absent" has exactly one representation
  // (API_CONTRACT_PHASE2.md). Do not add .url()/.email() refinements here --
  // owner-entered data is validated on write, and a strict check would reject
  // the whole payload (losing the opening hours and services too) over one
  // malformed field.
  address: z.string().nullable(),
  phone: z.string().nullable(),
  whatsapp: z.string().nullable(),
  email: z.string().nullable(),
  maps_url: z.string().nullable(),
  // The contract guarantees 7 entries ordered Monday(0) -> Sunday(6), but this
  // is deliberately not asserted with .length(7): rejecting the whole payload
  // over a missing hours row would also cost us the address and phone number,
  // which matter more to a visitor than the opening table.
  business_hours: z.array(businessHourSchema),
  content: salonContentSchema,
});
export type Salon = z.infer<typeof salonSchema>;

/* -------------------------------------------------------------------------- */
/* GET /services                                                               */
/* -------------------------------------------------------------------------- */

/** The trimmed category embedded in a service; the list form adds ordering. */
export const serviceCategoryRefSchema = z.object({
  id: z.uuid(),
  name: z.string(),
  slug: z.string(),
});
export type ServiceCategoryRef = z.infer<typeof serviceCategoryRefSchema>;

export const serviceCategorySchema = serviceCategoryRefSchema.extend({
  display_order: z.number().int(),
});
export type ServiceCategory = z.infer<typeof serviceCategorySchema>;

export const serviceSchema = z.object({
  id: z.uuid(),
  name: z.string(),
  slug: z.string(),
  description: z.string(),
  // Integer paise. A float here would mean the money path leaked a rounding
  // error upstream, so it must fail parsing rather than render.
  price_paise: z.number().int().nonnegative(),
  duration_minutes: z.number().int().nonnegative(),
  image_url: z.string().nullable(),
  is_featured: z.boolean(),
  display_order: z.number().int(),
  category: serviceCategoryRefSchema.nullable(),
});
export type Service = z.infer<typeof serviceSchema>;

export const serviceListSchema = z.object({
  categories: z.array(serviceCategorySchema),
  results: z.array(serviceSchema),
});
export type ServiceList = z.infer<typeof serviceListSchema>;

/* -------------------------------------------------------------------------- */
/* GET /gallery, /testimonials, /faqs                                          */
/* -------------------------------------------------------------------------- */

/** width/height are null when unknown; when present they reserve layout space. */
export const galleryImageSchema = z.object({
  id: z.uuid(),
  image_url: z.string(),
  alt_text: z.string(),
  caption: z.string().nullable(),
  display_order: z.number().int(),
  width: z.number().int().positive().nullable(),
  height: z.number().int().positive().nullable(),
});
export type GalleryImage = z.infer<typeof galleryImageSchema>;

export const gallerySchema = z.object({
  results: z.array(galleryImageSchema),
});
export type Gallery = z.infer<typeof gallerySchema>;

export const testimonialSchema = z.object({
  id: z.uuid(),
  author_name: z.string(),
  rating: z.number().int().min(1).max(5),
  body: z.string(),
  display_order: z.number().int(),
});
export type Testimonial = z.infer<typeof testimonialSchema>;

export const testimonialListSchema = z.object({
  results: z.array(testimonialSchema),
});
export type TestimonialList = z.infer<typeof testimonialListSchema>;

export const faqSchema = z.object({
  id: z.uuid(),
  question: z.string(),
  answer: z.string(),
  display_order: z.number().int(),
});
export type Faq = z.infer<typeof faqSchema>;

export const faqListSchema = z.object({
  results: z.array(faqSchema),
});
export type FaqList = z.infer<typeof faqListSchema>;

/* -------------------------------------------------------------------------- */
/* GET /legal/{slug}                                                           */
/* -------------------------------------------------------------------------- */

export const LEGAL_PAGE_SLUGS = [
  "terms",
  "privacy",
  "refunds",
  "promotion-rules",
] as const;

export const legalPageSlugSchema = z.enum(LEGAL_PAGE_SLUGS);
export type LegalPageSlug = z.infer<typeof legalPageSlugSchema>;

export const legalPageSchema = z.object({
  slug: legalPageSlugSchema,
  title: z.string(),
  body_markdown: z.string(),
  // Monotonic version of the published document. The promotion rules in force
  // at order time must stay recoverable, so this is surfaced, not hidden.
  version: z.number().int().positive(),
  // ISO-8601 UTC. Left as a plain string: nothing renders it as a Date yet, and
  // a stricter check would only add a way for the legal page to fail to load.
  published_at: z.string(),
});
export type LegalPage = z.infer<typeof legalPageSchema>;

/* -------------------------------------------------------------------------- */
/* POST /orders/quote                                                          */
/* -------------------------------------------------------------------------- */

/**
 * POST /orders/quote -- advisory only. The server recomputes at order time and
 * again at payment time, so nothing here is authoritative. Rendering it is the
 * only legitimate use.
 */
export const quoteLineSchema = z.object({
  service_id: z.uuid(),
  name: z.string(),
  unit_price_paise: z.number().int().nonnegative(),
  quantity: z.number().int().positive(),
  line_total_paise: z.number().int().nonnegative(),
  discount_alloc_paise: z.number().int().nonnegative(),
  net_paid_paise: z.number().int().nonnegative(),
});
export type QuoteLine = z.infer<typeof quoteLineSchema>;

export const quoteSchema = z.object({
  currency: z.literal("INR"),
  subtotal_paise: z.number().int().nonnegative(),
  /** The rate actually applied; 0 when the basket is not eligible. */
  discount_percent: z.number().int().min(0).max(100),
  /** The campaign's rate, applied or not -- used for the "unlock" prompt. */
  configured_discount_percent: z.number().int().min(0).max(100),
  discount_paise: z.number().int().nonnegative(),
  payable_paise: z.number().int().nonnegative(),
  eligible_for_discount: z.boolean(),
  distinct_service_count: z.number().int().nonnegative(),
  min_distinct_services: z.number().int().positive(),
  expires_at: z.string(),
  lines: z.array(quoteLineSchema),
});
export type Quote = z.infer<typeof quoteSchema>;

/** POST /orders response. `id` is the handle the payment step will need. */
export const orderItemSchema = z.object({
  service_name: z.string(),
  unit_price_paise: z.number().int().nonnegative(),
  quantity: z.number().int().positive(),
  line_total_paise: z.number().int().nonnegative(),
  discount_alloc_paise: z.number().int().nonnegative(),
  net_paid_paise: z.number().int().nonnegative(),
});

/**
 * The latest payment attempt. Only the last four digits of the customer's UPI
 * reference ever come back.
 */
export const orderPaymentSchema = z.object({
  status: z.enum(["not_started", "awaiting_confirmation", "confirmed", "rejected"]),
  method: z.enum(["upi_qr"]).nullable(),
  reference_last4: z.string().nullable(),
  rejection_reason: z.string().nullable(),
  submitted_at: z.string().nullable(),
  decided_at: z.string().nullable(),
});
export type OrderPayment = z.infer<typeof orderPaymentSchema>;

/**
 * Where the order stands in the daily draw. `held` means a place is kept while
 * the payment is checked -- it says nothing about winning, because nothing has
 * been decided.
 */
export const orderLuckySchema = z.object({
  status: z.enum(["pending", "held", "not_entered", "won", "not_won"]),
  reason: z
    .enum(["REPEAT_ENTRY", "DAY_FULL", "DAY_CLOSED", "HOLD_EXPIRED", "NOT_RUNNING"])
    .nullable(),
  participant_number: z.number().int().positive().nullable(),
  campaign_date: z.string().nullable(),
  refund_paise: z.number().int().nonnegative(),
  refund_status: z.enum(["pending", "sent"]).nullable(),
  free_services: z.array(z.string()),
});
export type OrderLucky = z.infer<typeof orderLuckySchema>;

export const orderSchema = z.object({
  id: z.uuid(),
  public_order_number: z.string(),
  status: z.string(),
  currency: z.literal("INR"),
  subtotal_paise: z.number().int().nonnegative(),
  discount_percent_applied: z.number().int().min(0).max(100),
  discount_paise: z.number().int().nonnegative(),
  total_paise: z.number().int().nonnegative(),
  created_at: z.string(),
  customer: z.object({
    name: z.string(),
    // The API returns the phone masked. There is no field here for the full
    // number because the response never carries one.
    phone_masked: z.string(),
  }),
  items: z.array(orderItemSchema),
  paid_at: z.string().nullable(),
  payment: orderPaymentSchema,
  lucky: orderLuckySchema,
});
export type Order = z.infer<typeof orderSchema>;

/**
 * GET /payments/options. `upi_qr` is the fallback while no payment gateway is
 * configured: the salon's own QR, confirmed by the owner by hand.
 */
export const paymentOptionsSchema = z.object({
  method: z.enum(["upi_qr", "gateway", "unavailable"]),
  upi_qr: z
    .object({
      qr_image_version: z.string(),
      upi_id: z.string().nullable(),
      payee_name: z.string().nullable(),
    })
    .nullable(),
});
export type PaymentOptions = z.infer<typeof paymentOptionsSchema>;
