import type { Metadata } from "next";

export const metadata: Metadata = { title: "Contact" };

export default function Page() {
  return (
    <article className="mx-auto max-w-3xl px-4 py-16">
      <h1 className="text-ivory-50 font-[family-name:var(--font-display-loaded)] text-3xl">
        Contact
      </h1>
      <p className="text-ivory-300 mt-4">
        This content is managed by the salon owner and served from the backend
        (LegalPage). Awaiting sign-off — see IMPLEMENTATION_PLAN.md Phase 0.
      </p>
    </article>
  );
}
