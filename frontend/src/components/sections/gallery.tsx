/**
 * Salon photo grid. Server component -- no lightbox yet; a plain grid keeps
 * the section keyboard-trivial and ships no JavaScript.
 */

import type { GalleryImage } from "@/types/api";

import { Section } from "./section";
import { SiteImage } from "./site-image";

const TILE_SIZES = "(min-width: 1024px) 272px, (min-width: 640px) 30vw, 45vw";

/** Used only to reserve the box when the API does not know the dimensions. */
const FALLBACK_WIDTH = 1200;
const FALLBACK_HEIGHT = 900;

export function GallerySection({ images }: { images: GalleryImage[] }) {
  // #gallery is a navbar link, so the section stays even with nothing in it.
  if (images.length === 0) {
    return (
      <Section id="gallery" title="Gallery">
        <p className="text-ivory-500 text-sm">Photos of the salon are on their way.</p>
      </Section>
    );
  }

  return (
    <Section id="gallery" title="Gallery">
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {images.map((image) => (
          <li
            key={image.id}
            className="border-ink-700/60 bg-ink-800 rounded-card overflow-hidden border"
          >
            <figure>
              <div className="aspect-4/3 w-full overflow-hidden">
                <SiteImage
                  src={image.image_url}
                  alt={image.alt_text}
                  // The payload's real dimensions when it has them, a 4:3
                  // stand-in when it does not. Either way the tile is sized
                  // before the bytes arrive.
                  width={image.width ?? FALLBACK_WIDTH}
                  height={image.height ?? FALLBACK_HEIGHT}
                  sizes={TILE_SIZES}
                  className="h-full w-full object-cover"
                />
              </div>
              {image.caption ? (
                <figcaption className="text-ivory-500 px-3 py-2 text-xs">
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
