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
import { CampaignSection } from "@/components/sections/campaign";
import { CraftBand } from "@/components/sections/craft-band";
import { CtaBand } from "@/components/sections/cta-band";
import { Hero } from "@/components/sections/hero";
import { GallerySection } from "@/components/sections/gallery";
import { HowItWorksSection } from "@/components/sections/how-it-works";
import { LocationSection } from "@/components/sections/location";
import { ServicesSection } from "@/components/sections/services";
import { TestimonialsSection } from "@/components/sections/testimonials";
import { WhyChooseUsSection } from "@/components/sections/why-choose-us";
import {
  getFaqs,
  getGallery,
  getPaymentMethod,
  getSalon,
  getServices,
  getTestimonials,
} from "@/lib/site-data";
import { faqJsonLd, localBusinessJsonLd, serviceJsonLd } from "@/lib/structured-data";

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
  const [salon, services, gallery, testimonials, faqs, paymentMethod] = await Promise.all(
    [
      getSalon(),
      getServices(),
      getGallery(),
      getTestimonials(),
      getFaqs(),
      getPaymentMethod(),
    ],
  );

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

      <Hero paymentMethod={paymentMethod} />

      {/* Live counters from GET /promotion/today. Client-rendered and polled,
          because a baked-in slot count goes stale the moment anyone books. */}
      <CampaignSection />

      <ServicesSection services={services} />

      {/* The discount reveal lives in the sticky selection bar (mounted in the
          root layout), so it follows the customer down the page rather than
          sitting in one section. */}

      <HowItWorksSection paymentMethod={paymentMethod} />

      {/* A decorative strip of the craft: photos and clay art drifting by. */}
      <CraftBand />

      <GallerySection images={gallery} />
      <TestimonialsSection testimonials={testimonials} />

      {salon ? <WhyChooseUsSection items={salon.content.why_choose_us} /> : null}

      {/* Always rendered, even with salon === null: the navbar links to
          #contact from every page, so the anchor must exist. The section
          handles its own empty state. */}
      <LocationSection salon={salon} />

      <CtaBand />

      <FaqSection faqs={faqs} />
    </>
  );
}
