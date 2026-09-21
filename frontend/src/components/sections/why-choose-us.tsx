import Image from "next/image";

import whyPhoto from "@/assets/photos/trendy-haircut.webp";

import { ClockArt, MedalArt, ShieldArt, TagArt } from "@/components/clay/clay-art";
import type { WhyChooseUsItem } from "@/types/api";

import { Section } from "./section";

/** The owner writes the copy; the illustrations cycle so each point has one. */
const ART = [
  { Art: MedalArt, tile: "bg-rose" },
  { Art: ShieldArt, tile: "bg-mint" },
  { Art: TagArt, tile: "bg-peach" },
  { Art: ClockArt, tile: "bg-sky" },
];

export function WhyChooseUsSection({ items }: { items: WhyChooseUsItem[] }) {
  if (items.length === 0) return null;

  return (
    <Section id="why-us" eyebrow="Why choose us" title="Grooming you can feel good about">
      <div className="grid items-center gap-8 lg:grid-cols-[1fr_1.35fr]">
        <div className="clay p-3 sm:p-4">
          <div className="relative aspect-4/5 overflow-hidden rounded-[1.5rem] lg:aspect-3/4">
            <Image
              src={whyPhoto}
              placeholder="blur"
              alt="A barber finishing a client's haircut in a bright barbershop"
              fill
              sizes="(min-width: 1024px) 420px, 90vw"
              className="object-cover"
            />
            <p className="absolute right-3 bottom-3 rounded-full bg-black/55 px-2.5 py-1 text-xs font-semibold text-white">
              Photo: Nenad Stojkovic · CC BY 2.0
            </p>
          </div>
        </div>

        <ul className="grid gap-5 sm:grid-cols-2">
          {items.map((item, index) => {
            const { Art, tile } = ART[index % ART.length];
            return (
              <li key={`${index}-${item.title}`} className="clay p-6">
                <div
                  className={`${tile} flex h-16 w-16 items-center justify-center rounded-2xl`}
                >
                  <Art size={48} />
                </div>
                <h3 className="font-display text-ink mt-4 text-xl">{item.title}</h3>
                <p className="text-ink-soft mt-2 text-sm leading-relaxed">{item.body}</p>
              </li>
            );
          })}
        </ul>
      </div>
    </Section>
  );
}
