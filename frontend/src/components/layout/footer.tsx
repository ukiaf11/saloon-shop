const POLICY_LINKS = [
  { href: "/terms", label: "Terms" },
  { href: "/privacy", label: "Privacy" },
  { href: "/refunds", label: "Refund Policy" },
  { href: "/promotion-rules", label: "Promotion Rules" },
];

export function Footer({ salonName }: { salonName: string }) {
  return (
    <footer className="border-ink-700/60 bg-ink-900 border-t">
      <div className="mx-auto max-w-6xl px-4 py-10">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-ivory-50 font-[family-name:var(--font-display-loaded)] text-lg">
            {salonName}
          </p>
          <nav aria-label="Policies">
            <ul className="flex flex-wrap gap-x-6 gap-y-2">
              {POLICY_LINKS.map((link) => (
                <li key={link.href}>
                  <a
                    href={link.href}
                    className="text-ivory-500 hover:text-gold-400 text-sm transition-colors"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        </div>
        <p className="text-ivory-500 mt-8 text-xs">
          © {new Date().getFullYear()} {salonName}. Daily promotional capacity and
          campaign rules apply.
        </p>
      </div>
    </footer>
  );
}
