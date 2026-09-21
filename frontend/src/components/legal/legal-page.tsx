import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { getLegalPage } from "@/lib/site-data";
import type { LegalPageSlug } from "@/types/api";

/**
 * Renders an owner-published legal page.
 *
 * The body is Markdown authored by the salon owner in the admin panel. It is
 * rendered with react-markdown, which does NOT pass raw HTML through by
 * default -- that default is deliberate and must not be relaxed with
 * rehype-raw. These pages are the binding promotion and refund terms, so an
 * injected script here would be both an XSS vector and a legal problem.
 *
 * remark-gfm is enabled because the promotion rules realistically need tables
 * (service tiers, refund windows) and strikethrough for superseded clauses.
 * Without it a pipe table renders as a run-on line of "|" characters in a
 * legally binding document. GFM adds no HTML passthrough, so the XSS posture
 * is unchanged.
 */
export async function LegalPage({
  slug,
  fallbackTitle,
}: {
  slug: LegalPageSlug;
  fallbackTitle: string;
}) {
  const page = await getLegalPage(slug);

  return (
    <article className="mx-auto max-w-3xl px-4 py-12 sm:py-16">
      <div className="clay p-6 sm:p-10">
        <h1 className="font-display text-ink text-4xl">{page?.title ?? fallbackTitle}</h1>

        {page ? (
          <>
            <p className="text-ink-muted mt-3 text-sm font-semibold">
              Version {page.version}
              {page.published_at
                ? ` · published ${new Date(page.published_at).toLocaleDateString(
                    "en-IN",
                    {
                      day: "numeric",
                      month: "short",
                      year: "numeric",
                      timeZone: "Asia/Kolkata",
                    },
                  )}`
                : null}
            </p>
            <div className="legal-prose mt-8">
              <Markdown remarkPlugins={[remarkGfm]}>{page.body_markdown}</Markdown>
            </div>
          </>
        ) : (
          // An unpublished page is a normal pre-launch state, not an error. Say so
          // plainly rather than showing a 404 -- the route is linked from the
          // footer of every page.
          <p className="bg-butter text-ink mt-6 rounded-2xl px-5 py-4 font-semibold">
            This page has not been published yet. Please contact the salon directly if you
            need these terms before they are available here.
          </p>
        )}
      </div>
    </article>
  );
}
