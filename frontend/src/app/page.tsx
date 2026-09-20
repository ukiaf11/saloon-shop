/**
 * The public single page.
 *
 * A server component: every section below renders from data fetched here, in
 * one parallel round of requests, so nothing waterfalls and the browser gets no
 * fetching code. Each reader degrades to null/[] on failure (see lib/site-data)
 * and each section handles its own empty state, so an API outage costs us a
 * section, never the page.
 */

import { FaqSection } from "@/components/sections/faq";
import { GallerySection } from "@/components/sections/gallery";
import { HowItWorksSection } from "@/components/sections/how-it-works";
import { LocationSection } from "@/components/sections/location";
import { OpeningHoursSection } from "@/components/sections/opening-hours";
import { ServicesSection } from "@/components/sections/services";
import { TestimonialsSection } from "@/components/sections/testimonials";
import { WhyChooseUsSection } from "@/components/sections/why-choose-us";
import {
  getFaqs,
  getGallery,
  getSalon,
  getServices,
  getTestimonials,
} from "@/lib/site-data";
import { faqJsonLd, localBusinessJsonLd, serviceJsonLd } from "@/lib/structured-data";

/**
 * Signed-off marketing copy, held here rather than read from SiteContent.
 *
 * "Har Din 5 Lucky Slots" is the wording the owner is signing off on, and the
 * campaign design hangs off it (memory.md sections 4 and 6). It should not be
 * able to change through a content edit, or vanish because /salon was briefly
 * unreachable at build time. The backend serves the same strings as its
 * SiteContent defaults; wire the hero to them once the wording is final.
 */
const HERO = {
  eyebrow: "Premium grooming. Daily rewards.",
  heading: "Har Din 5 Lucky Slots",
} as const;

/** How many gallery images to advertise in the LocalBusiness markup. */
const JSON_LD_IMAGE_LIMIT = 3;

/**
 * JSON.stringify does not escape "<", so a literal "</script>" inside
 * owner-authored FAQ or testimonial text would close the tag early. Escaping it
 * keeps the payload valid JSON and inert in the document.
 */
function jsonLd(data: unknown): { __html: string } {
  return { __html: JSON.stringify(data).replace(/</g, "\\u003c") };
}

export default async function Home() {
  const [salon, services, gallery, testimonials, faqs] = await Promise.all([
    getSalon(),
    getServices(),
    getGallery(),
    getTestimonials(),
    getFaqs(),
  ]);

  // schema.org wants absolute URLs. Relative paths would be resolved against
  // the crawler's idea of the base, so only fully-qualified ones are offered.
  const jsonLdImages = gallery
    .map((image) => image.image_url)
    .filter((url) => url.startsWith("http"))
    .slice(0, JSON_LD_IMAGE_LIMIT);

  return (
    <>
      {/* Structured data. Both payloads are built on the server from our own
          API response -- never from anything a visitor submitted -- which is
          why dangerouslySetInnerHTML is the documented Next.js pattern here. */}
      {salon ? (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={jsonLd(
            localBusinessJsonLd(salon, { images: jsonLdImages }),
          )}
        />
      ) : null}
      {salon && services.results.length > 0 ? (
        <script
          type="application/ld+json"
          // One script holding an array of nodes; JSON-LD allows that and it
          // beats emitting a tag per service.
          dangerouslySetInnerHTML={jsonLd(
            services.results.map((service) => serviceJsonLd(service, salon)),
          )}
        />
      ) : null}
      {faqs.length > 0 ? (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={jsonLd(faqJsonLd(faqs))}
        />
      ) : null}

      <section className="mx-auto max-w-6xl px-4 py-20 sm:py-28">
        <p className="text-gold-500 text-xs tracking-[0.2em] uppercase">{HERO.eyebrow}</p>
        <h1 className="text-ivory-50 mt-5 max-w-3xl font-[family-name:var(--font-display-loaded)] text-4xl leading-tight sm:text-6xl">
          {HERO.heading}
        </h1>
        <p className="text-ivory-300 mt-5 max-w-xl text-lg">
          Hair Cutting + Shaving + Face Massage — free for the day&apos;s lucky slots.
          Pick two or more services and save 10% automatically.
        </p>
        <div className="mt-9 flex flex-wrap gap-3">
          <a
            href="#services"
            className="bg-gold-500 text-ink-950 hover:bg-gold-400 rounded-full px-7 py-3 font-medium transition-colors"
          >
            Book Now
          </a>
          <a
            href="#services"
            className="border-ink-600 text-ivory-100 hover:border-gold-500 rounded-full border px-7 py-3 font-medium transition-colors"
          >
            View Services
          </a>
        </div>
        <p className="text-ivory-500 mt-6 text-xs">
          Daily promotional capacity and campaign rules apply.{" "}
          <a href="/promotion-rules" className="hover:text-gold-400 underline">
            View promotion rules
          </a>
        </p>
      </section>

      {/* Phase 4 mounts CampaignProgressCard here (live slots and winners, from
          GET /promotion/today). The anchor exists now so the id does not move
          under anyone later. */}
      <div id="campaign" className="scroll-mt-16" />

      <ServicesSection services={services} />

      {/* Phase 3: the discount reveal fires when the second distinct service is
          selected. It needs the selection state that Phase 3 introduces, so
          nothing is rendered for it yet -- see IMPLEMENTATION_PLAN.md. */}

      <HowItWorksSection />

      <GallerySection images={gallery} />
      <TestimonialsSection testimonials={testimonials} />

      {salon ? (
        <>
          <WhyChooseUsSection items={salon.content.why_choose_us} />
          <OpeningHoursSection hours={salon.business_hours} />
        </>
      ) : null}

      {/* Always rendered, even with salon === null: the navbar links to
          #contact from every page, so the anchor must exist. The section
          handles its own empty state. */}
      <LocationSection salon={salon} />

      <FaqSection faqs={faqs} />
    </>
  );
}
