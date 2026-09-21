import type { Metadata } from "next";

import credits from "@/assets/photos/credits.json";

export const metadata: Metadata = { title: "Photo credits" };

type Credit = {
  file: string;
  title: string;
  author: string;
  license: string;
  license_url: string;
  source: string;
};

/**
 * Attribution for third-party photography. The CC BY licences these images are
 * used under require it; the list is generated from credits.json, which is
 * written by the same script that downloads the images, so the two cannot
 * drift apart.
 */
export default function Page() {
  return (
    <article className="mx-auto max-w-3xl px-4 py-12 sm:py-16">
      <div className="clay p-6 sm:p-10">
        <h1 className="font-display text-ink text-4xl">Photo credits</h1>
        <p className="text-ink-soft mt-4">
          Illustrations on this site are original. The photographs below are used under
          the licences shown, via Wikimedia Commons.
        </p>
        <ul className="mt-8 space-y-4">
          {(credits as Credit[]).map((c) => (
            <li key={c.file} className="clay-well px-5 py-4">
              <p className="text-ink font-bold">{c.title}</p>
              <p className="text-ink-soft mt-1 text-sm">
                By {c.author} ·{" "}
                {c.license_url ? (
                  <a
                    href={c.license_url}
                    className="text-primary underline"
                    rel="license noopener"
                  >
                    {c.license}
                  </a>
                ) : (
                  c.license
                )}{" "}
                ·{" "}
                <a href={c.source} className="text-primary underline" rel="noopener">
                  source
                </a>
              </p>
            </li>
          ))}
        </ul>
      </div>
    </article>
  );
}
