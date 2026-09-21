/**
 * Address, contact routes, directions and opening hours. Server component.
 *
 * No embedded map iframe: it would load third-party scripts and cookies into
 * every visit for something a "Get directions" link does better on a phone,
 * where the tap should open the native maps app. maps_url is the owner's own
 * link, so nothing is guessed from the address.
 *
 * The hours sit here, beside the address, because they are what someone
 * planning a visit reads together.
 */

import { MapPinArt } from "@/components/clay/clay-art";
import type { Salon } from "@/types/api";

import { OpeningHoursCard } from "./opening-hours";
import { Section } from "./section";

/** wa.me wants bare digits; the API stores E.164 ("+919000000000"). */
function whatsappHref(number: string): string {
  return `https://wa.me/${number.replace(/\D/g, "")}`;
}

function ContactRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="clay-well px-4 py-3">
      <dt className="text-ink-muted text-xs font-extrabold tracking-[0.12em] uppercase">
        {label}
      </dt>
      <dd className="text-ink mt-1 font-semibold break-words">{children}</dd>
    </div>
  );
}

const LINK_CLASS = "text-primary underline underline-offset-4 hover:text-primary-hover";

export function LocationSection({ salon }: { salon: Salon | null }) {
  const social = salon?.content.social_links;
  const socials = [
    { label: "Instagram", href: social?.instagram },
    { label: "Facebook", href: social?.facebook },
  ].filter((link): link is { label: string; href: string } => Boolean(link.href));

  const hasContactDetails = Boolean(
    salon?.address || salon?.phone || salon?.whatsapp || salon?.email,
  );
  const hasAnything = hasContactDetails || Boolean(salon?.maps_url) || socials.length > 0;
  const hours = salon?.business_hours ?? [];

  // The section always renders, even with nothing to show. The navbar links to
  // #contact from every page, so dropping the anchor would leave a dead nav
  // item -- worse than an honest "not listed yet" line.
  return (
    <Section id="contact" eyebrow="Visit us" title="Come in and say hello">
      <div className="grid items-start gap-6 lg:grid-cols-2">
        <div className="clay p-6 sm:p-8">
          <h3 className="font-display text-ink text-2xl">Find us</h3>

          {hasAnything ? (
            <>
              {hasContactDetails ? (
                <address className="not-italic">
                  <dl className="mt-5 grid gap-3">
                    {salon?.address ? (
                      <ContactRow label="Address">{salon.address}</ContactRow>
                    ) : null}
                    {salon?.phone ? (
                      <ContactRow label="Phone">
                        <a href={`tel:${salon.phone}`} className={LINK_CLASS}>
                          {salon.phone}
                        </a>
                      </ContactRow>
                    ) : null}
                    {salon?.whatsapp ? (
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
                    {salon?.email ? (
                      <ContactRow label="Email">
                        <a href={`mailto:${salon.email}`} className={LINK_CLASS}>
                          {salon.email}
                        </a>
                      </ContactRow>
                    ) : null}
                  </dl>
                </address>
              ) : null}

              <div className="mt-6 flex flex-wrap gap-3">
                {salon?.maps_url ? (
                  <a
                    href={salon.maps_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="clay-btn inline-flex items-center gap-2 px-6 py-3 text-sm font-bold"
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
                        strokeWidth="2.2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </a>
                ) : null}
                {socials.map((link) => (
                  <a
                    key={link.label}
                    href={link.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="clay-btn-soft px-5 py-3 text-sm font-bold"
                  >
                    {link.label}
                  </a>
                ))}
              </div>
            </>
          ) : (
            <div className="mt-6 flex flex-col items-center gap-4 text-center sm:flex-row sm:text-left">
              <div className="bg-peach flex h-24 w-24 shrink-0 items-center justify-center rounded-[1.75rem]">
                <MapPinArt size={72} />
              </div>
              <p className="text-ink-soft leading-relaxed">
                Contact details are not listed yet. Please drop in during the opening
                hours.
              </p>
            </div>
          )}
        </div>

        <OpeningHoursCard hours={hours} />
      </div>
    </Section>
  );
}
