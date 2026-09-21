import Image from "next/image";

// Imported rather than referenced by path. A string src like
// "/images/x.webp" is NOT prefixed with basePath when images are unoptimized,
// which the static GitHub Pages export requires -- every photo 404'd there.
// An import is rewritten by the bundler, content-hashed for caching, and gets
// width, height and a blur placeholder for free.
import bandPhoto from "@/assets/photos/barber-comb-wide.webp";

/** A closing call to action over the wide photo, before the FAQ. */
export function CtaBand() {
  return (
    <section className="px-4 py-6 sm:py-8">
      <div className="clay relative mx-auto max-w-6xl overflow-hidden p-3 sm:p-4">
        <div className="relative overflow-hidden rounded-[1.5rem]">
          <Image
            src={bandPhoto}
            placeholder="blur"
            alt=""
            fill
            sizes="(min-width: 1152px) 1120px, 95vw"
            className="object-cover"
          />
          {/* A warm scrim keeps the headline above 4.5:1 over the photo. */}
          <div
            aria-hidden="true"
            className="absolute inset-0 bg-gradient-to-r from-[#3a2a22]/90 via-[#3a2a22]/70 to-[#3a2a22]/20"
          />
          <div className="relative px-6 py-14 sm:px-12 sm:py-20">
            <h2 className="font-display max-w-lg text-3xl leading-tight text-white sm:text-5xl">
              Your chair is waiting — and it might be a lucky one.
            </h2>
            <p className="mt-4 max-w-md text-base text-white/90 sm:text-lg">
              Book two or more services, save 10%, and take today&apos;s next slot.
            </p>
            <a
              href="#services"
              className="clay-btn mt-8 inline-block px-8 py-4 text-base font-bold"
            >
              Book now
            </a>
          </div>
          <p className="absolute right-3 bottom-3 rounded-full bg-black/55 px-2.5 py-1 text-xs font-semibold text-white">
            Photo: Nenad Stojkovic · CC BY 2.0
          </p>
        </div>
      </div>
    </section>
  );
}
