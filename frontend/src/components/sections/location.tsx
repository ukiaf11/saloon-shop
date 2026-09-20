/**
 * Address, contact routes and directions. Server component.
 *
 * No embedded map iframe: it would load third-party scripts and cookies into
 * every visit for something a "Get directions" link does better on a phone,
 * where the tap should open the native maps app. maps_url is the owner's own
 * link, so nothing is guessed from the address.
 */

import type { Salon } from "@/types/api";

import { Section } from "./section";

/** wa.me wants bare digits; the API stores E.164 ("+919000000000"). */
function whatsappHref(number: string): string {
  return `https://wa.me/${number.replace(/\D/g, "")}`;
}

function ContactRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="border-ink-800 border-b py-3 last:border-b-0">
      <dt className="text-ivory-500 text-xs tracking-wide uppercase">{label}</dt>
      <dd className="text-ivory-100 mt-1 text-sm break-words">{children}</dd>
    </div>
  );
}

const LINK_CLASS = "hover:text-gold-400 underline underline-offset-4 transition-colors";

export function LocationSection({ salon }: { salon: Salon | null }) {
  const social = salon?.content.social_links;
  const socials = [
    { label: "Instagram", href: social?.instagram },
    { label: "Facebook", href: social?.facebook },
  ].filter((link): link is { label: string; href: string } => Boolean(link.href));

  const hasContactDetails = Boolean(
    salon?.address || salon?.phone || salon?.whatsapp || salon?.email,
  );

  // The section always renders, even with nothing to show. The navbar links to
  // #contact from every page, so dropping the anchor would leave a dead nav
  // item -- worse than an honest "not listed yet" line.
  if (!salon || (!hasContactDetails && !salon.maps_url && socials.length === 0)) {
    return (
      <Section id="contact" title="Find us">
        <p className="text-ivory-300 max-w-prose text-sm">
          Contact details are not listed yet. Please visit the salon during the opening
          hours above.
        </p>
      </Section>
    );
  }

  return (
    <Section id="contact" title="Find us">
      <div className="grid gap-8 lg:grid-cols-2">
        {hasContactDetails ? (
          <address className="not-italic">
            <dl className="border-ink-700/60 bg-ink-900 rounded-card border px-5">
              {salon.address ? (
                <ContactRow label="Address">{salon.address}</ContactRow>
              ) : null}
              {salon.phone ? (
                <ContactRow label="Phone">
                  <a href={`tel:${salon.phone}`} className={LINK_CLASS}>
                    {salon.phone}
                  </a>
                </ContactRow>
              ) : null}
              {salon.whatsapp ? (
                <ContactRow label="WhatsApp">
                  <a
                    href={whatsappHref(salon.whatsapp)}
                    className={LINK_CLASS}
                    rel="noopener noreferrer"
                    target="_blank"
                  >
                    {salon.whatsapp}
                  </a>
                </ContactRow>
              ) : null}
              {salon.email ? (
                <ContactRow label="Email">
                  <a href={`mailto:${salon.email}`} className={LINK_CLASS}>
                    {salon.email}
                  </a>
                </ContactRow>
              ) : null}
            </dl>
          </address>
        ) : null}

        <div className="flex flex-col gap-5">
          {salon.maps_url ? (
            <a
              href={salon.maps_url}
              target="_blank"
              rel="noopener noreferrer"
              className="bg-gold-500 text-ink-950 hover:bg-gold-400 inline-flex w-fit items-center gap-2 rounded-full px-6 py-3 text-sm font-medium transition-colors"
            >
              Get directions
              <span className="sr-only">(opens Google Maps in a new tab)</span>
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                aria-hidden="true"
              >
                <path
                  d="M7 17L17 7M17 7H9M17 7v8"
                  stroke="currentColor"
                  strokeWidth="1.75"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </a>
          ) : null}

          {socials.length > 0 ? (
            <nav aria-label="Social profiles">
              <ul className="flex flex-wrap gap-x-6 gap-y-2">
                {socials.map((link) => (
                  <li key={link.label}>
                    <a
                      href={link.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={`text-ivory-300 text-sm ${LINK_CLASS}`}
                    >
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </nav>
          ) : null}
        </div>
      </div>
    </Section>
  );
}
