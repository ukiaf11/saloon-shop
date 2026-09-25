/**
 * The services section. A server component that hands the API payload to the
 * client-side browser, which owns the category filter.
 *
 * The banner photo above the grid is editorial: it shows the craft, and its
 * caption points at the daily reward. It is not a service image -- those come
 * from the API when the owner uploads them.
 */

import Image from "next/image";

import shavePhoto from "@/assets/photos/beard-shave.webp";

import { Reveal } from "@/components/reveal";
import type { ServiceList } from "@/types/api";

import { Section } from "./section";
import { ServiceBrowser } from "./service-browser";

function CraftBanner() {
  return (
    <Reveal className="clay clay-lift mb-8 p-3 sm:mb-10 sm:p-4">
      <div className="relative overflow-hidden rounded-[1.5rem]">
        <div className="relative aspect-16/7 sm:aspect-16/5">
          <Image
            src={shavePhoto}
            placeholder="blur"
            alt="A barber shaving a client's beard with a straight razor"
            fill
            sizes="(min-width: 1152px) 1088px, 94vw"
            className="lift-media object-cover object-[50%_38%]"
          />
        </div>
        {/* Scrim keeps the caption at AA over the photo's bright areas. */}
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-gradient-to-t from-[#3a2a22]/85 via-[#3a2a22]/25 to-transparent"
        />
        <div className="absolute right-4 bottom-4 left-4 flex flex-wrap items-end justify-between gap-3 sm:right-6 sm:bottom-5 sm:left-6">
          <div>
            <p className="font-display text-xl text-white sm:text-2xl">
              The classic straight-razor shave
            </p>
            <p className="mt-1 text-sm font-semibold text-white/90">
              Free for today&apos;s lucky slots — with the haircut and face massage.
            </p>
          </div>
          <p className="rounded-full bg-black/55 px-2.5 py-1 text-xs font-semibold text-white">
            Photo: Nenad Stojkovic · CC BY 2.0
          </p>
        </div>
      </div>
    </Reveal>
  );
}

export function ServicesSection({ services }: { services: ServiceList }) {
  const { categories, results } = services;

  // The section keeps its anchor even when empty: #services is a navbar link
  // and a dead anchor is worse than a quiet line of text.
  if (results.length === 0) {
    return (
      <Section id="services" eyebrow="Our services" title="What we do best">
        <p className="clay text-ink-soft p-8">
          Our service list is being updated. Call the salon and we will walk you through
          it.
        </p>
      </Section>
    );
  }

  return (
    <Section
      id="services"
      eyebrow="Our services"
      title="What we do best"
      description="Pick two or more different services and 10% comes off automatically at checkout."
      revealChildren={false}
    >
      <CraftBanner />
      <ServiceBrowser categories={categories} services={results} />
    </Section>
  );
}
