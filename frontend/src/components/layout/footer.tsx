import { ScissorsArt } from "@/components/clay/clay-art";

const POLICY_LINKS = [
  { href: "/terms", label: "Terms" },
  { href: "/privacy", label: "Privacy" },
  { href: "/refunds", label: "Refund policy" },
  { href: "/promotion-rules", label: "Promotion rules" },
];

export function Footer({ salonName }: { salonName: string }) {
  return (
    <footer className="px-4 pt-8 pb-10">
      <div className="clay mx-auto max-w-6xl px-6 py-10 sm:px-10">
        <div className="flex flex-col gap-8 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <span className="bg-peach flex h-12 w-12 items-center justify-center rounded-full">
              <ScissorsArt size={36} />
            </span>
            <div>
              <p className="font-display text-ink text-xl">{salonName}</p>
              <p className="text-ink-muted text-sm">Premium grooming. Daily rewards.</p>
            </div>
          </div>
          <nav aria-label="Policies">
            <ul className="flex flex-wrap gap-2">
              {POLICY_LINKS.map((link) => (
                <li key={link.href}>
                  <a
                    href={link.href}
                    className="clay-btn-soft text-ink-soft hover:text-ink inline-flex min-h-11 items-center px-4 text-sm font-semibold"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        </div>
        <p className="text-ink-muted mt-8 text-xs">
          © {new Date().getFullYear()} {salonName}. Daily promotional capacity and
          campaign rules apply.{" "}
          <a href="/credits" className="hover:text-ink underline">
            Photo credits
          </a>
        </p>
      </div>
    </footer>
  );
}
