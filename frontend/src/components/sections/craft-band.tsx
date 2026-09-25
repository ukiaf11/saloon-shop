import Image from "next/image";

import shavePhoto from "@/assets/photos/beard-shave.webp";
import portraitPhoto from "@/assets/photos/barber-comb-portrait.webp";
import widePhoto from "@/assets/photos/barber-comb-wide.webp";
import trendyPhoto from "@/assets/photos/trendy-haircut.webp";

import { CombArt, RazorArt, ScissorsArt, StarArt } from "@/components/clay/clay-art";

/**
 * A slow film-strip of the craft between sections: photography interleaved
 * with the site's clay illustrations, looping seamlessly.
 *
 * Decorative by construction, so the whole band is aria-hidden and none of
 * the images carry alt text -- every photo here also appears elsewhere on the
 * page with its credit, and all are listed on /credits. With reduced motion
 * (or no JS) the animation never runs and it reads as a static strip.
 */

const TILE_SIZES = "260px";

function PhotoTile({ src }: { src: typeof shavePhoto }) {
  return (
    <li className="clay w-56 shrink-0 p-2.5 sm:w-64">
      <div className="aspect-16/11 overflow-hidden rounded-[1.25rem]">
        <Image
          src={src}
          alt=""
          sizes={TILE_SIZES}
          className="h-full w-full object-cover"
        />
      </div>
    </li>
  );
}

function ArtTile({ tile, children }: { tile: string; children: React.ReactNode }) {
  return (
    <li
      className={`clay-sm ${tile} flex aspect-16/11 w-40 shrink-0 items-center justify-center sm:w-44`}
    >
      {children}
    </li>
  );
}

function Tiles() {
  return (
    <>
      <PhotoTile src={portraitPhoto} />
      <ArtTile tile="bg-peach">
        <ScissorsArt size={92} />
      </ArtTile>
      <PhotoTile src={shavePhoto} />
      <ArtTile tile="bg-butter">
        <StarArt size={92} />
      </ArtTile>
      <PhotoTile src={trendyPhoto} />
      <ArtTile tile="bg-lavender">
        <RazorArt size={92} />
      </ArtTile>
      <PhotoTile src={widePhoto} />
      <ArtTile tile="bg-mint">
        <CombArt size={92} />
      </ArtTile>
    </>
  );
}

export function CraftBand() {
  return (
    <div aria-hidden="true" className="craft-band overflow-hidden py-6 sm:py-8">
      <ul className="craft-track flex w-max gap-5 pr-5">
        <Tiles />
        <Tiles />
      </ul>
    </div>
  );
}
