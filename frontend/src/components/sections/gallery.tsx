import type { GalleryImage } from "@/types/api";

import { Section } from "./section";
import { SiteImage } from "./site-image";

const TILE_SIZES = "(min-width: 1024px) 360px, (min-width: 640px) 45vw, 92vw";

const FALLBACK_WIDTH = 1200;
const FALLBACK_HEIGHT = 900;

/**
 * The salon's own photos, uploaded by the owner. Renders nothing until there
 * are some: filling it with stock photography would present someone else's
 * salon as this one. The navbar does not link here, so an absent section
 * leaves no dead anchor.
 */
export function GallerySection({ images }: { images: GalleryImage[] }) {
  if (images.length === 0) return null;

  return (
    <Section id="gallery" eyebrow="Gallery" title="Inside the salon">
      <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {images.map((image) => (
          <li key={image.id} className="clay p-3">
            <figure>
              <div className="aspect-4/3 w-full overflow-hidden rounded-[1.5rem]">
                <SiteImage
                  src={image.image_url}
                  alt={image.alt_text}
                  width={image.width ?? FALLBACK_WIDTH}
                  height={image.height ?? FALLBACK_HEIGHT}
                  sizes={TILE_SIZES}
                  className="h-full w-full object-cover"
                />
              </div>
              {image.caption ? (
                <figcaption className="text-ink-soft px-2 pt-3 pb-1 text-sm font-semibold">
                  {image.caption}
                </figcaption>
              ) : null}
            </figure>
          </li>
        ))}
      </ul>
    </Section>
  );
}
