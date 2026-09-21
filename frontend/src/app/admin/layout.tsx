import type { Metadata } from "next";

import { ScissorsArt } from "@/components/clay/clay-art";
import { SALON_NAME } from "@/lib/site";

export const metadata: Metadata = {
  title: "Owner",
  // Never indexed, whatever the site-wide setting says.
  robots: { index: false, follow: false },
};

export default function AdminLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <>
      <header className="px-4 pt-4">
        <div className="clay mx-auto flex max-w-4xl items-center gap-3 px-5 py-3">
          <span className="bg-peach flex h-10 w-10 items-center justify-center rounded-full">
            <ScissorsArt size={28} />
          </span>
          <p className="font-display text-ink text-lg">
            {SALON_NAME} <span className="text-ink-muted font-body text-sm">· Owner</span>
          </p>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-4xl px-4 py-8 sm:py-10">
        {children}
      </main>
    </>
  );
}
