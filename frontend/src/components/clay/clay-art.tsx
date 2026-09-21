/**
 * Clay-style illustrations, drawn in SVG.
 *
 * Original artwork rather than stock: no licence to track, crisp at any size,
 * a few hundred bytes each, and identical on every host including the static
 * GitHub Pages export. They are decorative, so each is aria-hidden; the text
 * beside it carries the meaning.
 *
 * The clay look comes from three layers on every shape:
 *   - a diagonal gradient (lighter top-left, deeper bottom-right),
 *   - a blurred white highlight near the top-left,
 *   - a soft offset drop shadow on the whole group.
 * Shapes are chunky with rounded ends -- clay has no thin lines.
 */

import { useId } from "react";

const PALETTE = {
  terracotta: "#e08a62",
  gold: "#f2c14e",
  peach: "#ffb894",
  lavender: "#b9a6f5",
  mint: "#86d6ae",
  sky: "#8cc4ee",
  rose: "#f59ab0",
  brown: "#9a6448",
  silver: "#c9c3d6",
  cream: "#fff8f0",
  ink: "#3a2a22",
} as const;

type Paint = keyof typeof PALETTE;

function mix(hex: string, toward: "#ffffff" | "#000000", amount: number): string {
  const parse = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const [r1, g1, b1] = parse(hex);
  const [r2, g2, b2] = parse(toward);
  const c = (a: number, b: number) => Math.round(a + (b - a) * amount);
  return `#${[c(r1, r2), c(g1, g2), c(b1, b2)]
    .map((v) => v.toString(16).padStart(2, "0"))
    .join("")}`;
}

/** Shared defs: one gradient per paint, plus the shadow and highlight blur. */
function Defs({ uid, paints }: { uid: string; paints: Paint[] }) {
  return (
    <defs>
      <filter id={`${uid}-drop`} x="-40%" y="-40%" width="180%" height="180%">
        <feDropShadow
          dx="2"
          dy="6"
          stdDeviation="5"
          floodColor="#6e462d"
          floodOpacity="0.28"
        />
      </filter>
      <filter id={`${uid}-blur`} x="-50%" y="-50%" width="200%" height="200%">
        <feGaussianBlur stdDeviation="3" />
      </filter>
      {paints.map((p) => (
        <linearGradient key={p} id={`${uid}-${p}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={mix(PALETTE[p], "#ffffff", 0.42)} />
          <stop offset="0.55" stopColor={PALETTE[p]} />
          <stop offset="1" stopColor={mix(PALETTE[p], "#000000", 0.14)} />
        </linearGradient>
      ))}
    </defs>
  );
}

type ArtProps = { className?: string; size?: number };

function Svg({
  className,
  size = 120,
  paints,
  children,
}: ArtProps & {
  paints: Paint[];
  children: (fill: (p: Paint) => string, uid: string) => React.ReactNode;
}) {
  // useId keeps gradient ids unique when the same art appears twice on a page;
  // duplicate SVG ids make the second copy render with the first one's paint.
  const uid = useId().replace(/:/g, "");
  const fill = (p: Paint) => `url(#${uid}-${p})`;
  return (
    <svg
      viewBox="0 0 120 120"
      width={size}
      height={size}
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <Defs uid={uid} paints={paints} />
      <g filter={`url(#${uid}-drop)`}>{children(fill, uid)}</g>
    </svg>
  );
}

/** A soft white highlight, the detail that makes a flat shape read as clay. */
function Shine({
  uid,
  cx,
  cy,
  rx,
  ry,
  opacity = 0.6,
}: {
  uid: string;
  cx: number;
  cy: number;
  rx: number;
  ry: number;
  opacity?: number;
}) {
  return (
    <ellipse
      cx={cx}
      cy={cy}
      rx={rx}
      ry={ry}
      fill="#fff"
      opacity={opacity}
      filter={`url(#${uid}-blur)`}
    />
  );
}

// --- services ---------------------------------------------------------------

export function ScissorsArt(props: ArtProps) {
  return (
    <Svg {...props} paints={["silver", "terracotta", "gold"]}>
      {(f, uid) => (
        <>
          <rect
            x="53"
            y="6"
            width="14"
            height="66"
            rx="7"
            fill={f("silver")}
            transform="rotate(30 60 64)"
          />
          <rect
            x="53"
            y="6"
            width="14"
            height="66"
            rx="7"
            fill={f("silver")}
            transform="rotate(-30 60 64)"
          />
          <circle cx="36" cy="90" r="19" fill={f("terracotta")} />
          <circle cx="84" cy="90" r="19" fill={f("terracotta")} />
          <circle cx="36" cy="90" r="8" fill={PALETTE.cream} />
          <circle cx="84" cy="90" r="8" fill={PALETTE.cream} />
          <circle cx="60" cy="63" r="7" fill={f("gold")} />
          <Shine uid={uid} cx={29} cy={82} rx={6} ry={4} />
          <Shine uid={uid} cx={77} cy={82} rx={6} ry={4} />
        </>
      )}
    </Svg>
  );
}

export function RazorArt(props: ArtProps) {
  return (
    <Svg {...props} paints={["sky", "gold", "silver"]}>
      {(f, uid) => (
        <>
          <rect x="51" y="44" width="18" height="66" rx="9" fill={f("gold")} />
          <rect x="47" y="98" width="26" height="14" rx="7" fill={f("gold")} />
          <rect x="24" y="16" width="72" height="32" rx="16" fill={f("sky")} />
          <rect
            x="31"
            y="27"
            width="58"
            height="8"
            rx="4"
            fill={PALETTE.cream}
            opacity="0.9"
          />
          <rect x="54" y="48" width="12" height="8" rx="4" fill={f("silver")} />
          <Shine uid={uid} cx={40} cy={22} rx={12} ry={4} />
          <Shine uid={uid} cx={57} cy={62} rx={3} ry={10} opacity={0.5} />
        </>
      )}
    </Svg>
  );
}

export function FaceArt(props: ArtProps) {
  return (
    <Svg {...props} paints={["peach", "rose", "gold"]}>
      {(f, uid) => (
        <>
          <circle cx="58" cy="64" r="40" fill={f("peach")} />
          <path
            d="M40 60 q7 7 14 0"
            fill="none"
            stroke={PALETTE.ink}
            strokeWidth="4.5"
            strokeLinecap="round"
          />
          <path
            d="M64 60 q7 7 14 0"
            fill="none"
            stroke={PALETTE.ink}
            strokeWidth="4.5"
            strokeLinecap="round"
          />
          <ellipse cx="38" cy="76" rx="8" ry="5" fill={f("rose")} />
          <ellipse cx="80" cy="76" rx="8" ry="5" fill={f("rose")} />
          <path
            d="M50 84 q9 7 18 0"
            fill="none"
            stroke={PALETTE.ink}
            strokeWidth="4"
            strokeLinecap="round"
          />
          <path d="M98 14 l4 10 10 4 -10 4 -4 10 -4 -10 -10 -4 10 -4z" fill={f("gold")} />
          <Shine uid={uid} cx={42} cy={40} rx={12} ry={7} />
        </>
      )}
    </Svg>
  );
}

export function DropletArt(props: ArtProps) {
  return (
    <Svg {...props} paints={["sky", "mint", "lavender"]}>
      {(f, uid) => (
        <>
          <path
            d="M58 10 C58 10 22 52 22 76 a36 36 0 0 0 72 0 C94 52 58 10 58 10 Z"
            fill={f("sky")}
          />
          <circle cx="96" cy="34" r="12" fill={f("mint")} />
          <circle cx="102" cy="62" r="7" fill={f("lavender")} />
          <Shine uid={uid} cx={42} cy={66} rx={7} ry={14} />
          <Shine uid={uid} cx={92} cy={30} rx={4} ry={3} />
        </>
      )}
    </Svg>
  );
}

export function BeardArt(props: ArtProps) {
  return (
    <Svg {...props} paints={["brown", "peach"]}>
      {(f, uid) => (
        <>
          <path
            d="M24 48 C24 90 40 112 60 112 C80 112 96 90 96 48 C86 62 74 66 60 66 C46 66 34 62 24 48 Z"
            fill={f("brown")}
          />
          <path
            d="M60 50 C50 38 28 38 16 50 C22 64 42 66 52 58 C56 55 58 54 60 54 C62 54 64 55 68 58 C78 66 98 64 104 50 C92 38 70 38 60 50 Z"
            fill={f("brown")}
          />
          <ellipse cx="60" cy="80" rx="11" ry="6" fill={f("peach")} />
          <Shine uid={uid} cx={32} cy={47} rx={8} ry={3} />
          <Shine uid={uid} cx={42} cy={82} rx={6} ry={10} opacity={0.35} />
        </>
      )}
    </Svg>
  );
}

export function StonesArt(props: ArtProps) {
  return (
    <Svg {...props} paints={["lavender", "mint", "sky"]}>
      {(f, uid) => (
        <>
          <ellipse cx="60" cy="96" rx="42" ry="16" fill={f("lavender")} />
          <ellipse cx="60" cy="70" rx="32" ry="14" fill={f("mint")} />
          <ellipse cx="60" cy="47" rx="23" ry="12" fill={f("sky")} />
          <path d="M60 30 C54 22 54 14 60 6 C66 14 66 22 60 30 Z" fill={f("mint")} />
          <Shine uid={uid} cx={40} cy={90} rx={12} ry={4} />
          <Shine uid={uid} cx={46} cy={65} rx={9} ry={3} />
          <Shine uid={uid} cx={50} cy={43} rx={7} ry={3} />
        </>
      )}
    </Svg>
  );
}

export function SwatchesArt(props: ArtProps) {
  return (
    <Svg {...props} paints={["rose", "gold", "lavender", "cream"]}>
      {(f, uid) => (
        <>
          <rect
            x="47"
            y="14"
            width="26"
            height="80"
            rx="13"
            fill={f("lavender")}
            transform="rotate(-26 60 96)"
          />
          <rect x="47" y="14" width="26" height="80" rx="13" fill={f("gold")} />
          <rect
            x="47"
            y="14"
            width="26"
            height="80"
            rx="13"
            fill={f("rose")}
            transform="rotate(26 60 96)"
          />
          <circle cx="60" cy="96" r="9" fill={f("cream")} />
          <Shine uid={uid} cx={55} cy={30} rx={4} ry={10} />
        </>
      )}
    </Svg>
  );
}

export function JarArt(props: ArtProps) {
  return (
    <Svg {...props} paints={["mint", "lavender", "gold"]}>
      {(f, uid) => (
        <>
          <rect x="24" y="44" width="72" height="62" rx="22" fill={f("mint")} />
          <rect x="30" y="28" width="60" height="22" rx="11" fill={f("lavender")} />
          <path d="M60 64 C48 64 44 76 48 88 C60 88 66 78 60 64 Z" fill={f("gold")} />
          <path
            d="M60 64 C72 64 76 76 72 88 C60 88 54 78 60 64 Z"
            fill={f("gold")}
            opacity="0.8"
          />
          <Shine uid={uid} cx={38} cy={58} rx={6} ry={12} />
          <Shine uid={uid} cx={46} cy={33} rx={12} ry={3} />
        </>
      )}
    </Svg>
  );
}

export function CombArt(props: ArtProps) {
  return (
    <Svg {...props} paints={["terracotta"]}>
      {(f, uid) => (
        <g transform="rotate(-18 60 60)">
          <rect x="14" y="34" width="92" height="24" rx="12" fill={f("terracotta")} />
          {Array.from({ length: 9 }, (_, i) => (
            <rect
              key={i}
              x={20 + i * 9.6}
              y="52"
              width="6"
              height="34"
              rx="3"
              fill={f("terracotta")}
            />
          ))}
          <Shine uid={uid} cx={40} cy={40} rx={18} ry={4} />
        </g>
      )}
    </Svg>
  );
}

// --- steps, badges and trust icons -----------------------------------------

export function ChecklistArt(props: ArtProps) {
  return (
    <Svg {...props} paints={["cream", "mint", "silver"]}>
      {(f, uid) => (
        <>
          <rect x="22" y="14" width="76" height="94" rx="20" fill={f("cream")} />
          {[36, 60, 84].map((y) => (
            <g key={y}>
              <circle cx="42" cy={y} r="9" fill={f("mint")} />
              <path
                d={`M37 ${y} l4 4 7 -8`}
                fill="none"
                stroke={PALETTE.ink}
                strokeWidth="3.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <rect x="57" y={y - 5} width="30" height="10" rx="5" fill={f("silver")} />
            </g>
          ))}
          <Shine uid={uid} cx={40} cy={20} rx={14} ry={3} />
        </>
      )}
    </Svg>
  );
}

export function CardArt(props: ArtProps) {
  return (
    <Svg {...props} paints={["terracotta", "gold", "cream"]}>
      {(f, uid) => (
        <>
          <rect x="12" y="30" width="96" height="64" rx="16" fill={f("terracotta")} />
          <rect x="12" y="44" width="96" height="12" fill={PALETTE.ink} opacity="0.25" />
          <rect x="24" y="64" width="22" height="16" rx="5" fill={f("gold")} />
          <rect
            x="54"
            y="70"
            width="40"
            height="7"
            rx="3.5"
            fill={f("cream")}
            opacity="0.85"
          />
          <Shine uid={uid} cx={34} cy={35} rx={16} ry={3} />
        </>
      )}
    </Svg>
  );
}

export function StarArt(props: ArtProps) {
  return (
    <Svg {...props} paints={["gold", "peach"]}>
      {(f, uid) => (
        <>
          <path
            d="M60 12 L73 44 L106 46 L80 67 L89 100 L60 82 L31 100 L40 67 L14 46 L47 44 Z"
            fill={f("gold")}
            stroke={f("gold")}
            strokeWidth="8"
            strokeLinejoin="round"
          />
          <path d="M100 12 l3 8 8 3 -8 3 -3 8 -3 -8 -8 -3 8 -3z" fill={f("peach")} />
          <path d="M16 90 l2 6 6 2 -6 2 -2 6 -2 -6 -6 -2 6 -2z" fill={f("peach")} />
          <Shine uid={uid} cx={50} cy={46} rx={10} ry={6} />
        </>
      )}
    </Svg>
  );
}

export function TicketArt(props: ArtProps) {
  return (
    <Svg {...props} paints={["cream", "lavender"]}>
      {(f, uid) => (
        <>
          <path
            d="M18 26 h84 a8 8 0 0 1 8 8 v14 a12 12 0 0 0 0 24 v14 a8 8 0 0 1 -8 8 h-84 a8 8 0 0 1 -8 -8 v-14 a12 12 0 0 0 0 -24 v-14 a8 8 0 0 1 8 -8 z"
            fill={f("cream")}
          />
          {[0, 1, 2].flatMap((r) =>
            [0, 1, 2].map((c) =>
              (r + c) % 2 === 0 || (r === 1 && c === 1) ? (
                <rect
                  key={`${r}${c}`}
                  x={34 + c * 13}
                  y={40 + r * 13}
                  width="10"
                  height="10"
                  rx="2.5"
                  fill={PALETTE.ink}
                />
              ) : null,
            ),
          )}
          <rect x="80" y="44" width="18" height="8" rx="4" fill={f("lavender")} />
          <rect x="80" y="58" width="12" height="8" rx="4" fill={f("lavender")} />
          <Shine uid={uid} cx={38} cy={31} rx={14} ry={3} />
        </>
      )}
    </Svg>
  );
}

export function MedalArt(props: ArtProps) {
  return (
    <Svg {...props} paints={["rose", "gold"]}>
      {(f, uid) => (
        <>
          <path d="M40 10 h16 l12 40 h-16 z" fill={f("rose")} />
          <path d="M80 10 h-16 l-12 40 h16 z" fill={f("rose")} />
          <circle cx="60" cy="74" r="34" fill={f("gold")} />
          <circle
            cx="60"
            cy="74"
            r="22"
            fill="none"
            stroke={PALETTE.cream}
            strokeWidth="4"
            opacity="0.7"
          />
          <Shine uid={uid} cx={46} cy={58} rx={10} ry={6} />
        </>
      )}
    </Svg>
  );
}

export function ShieldArt(props: ArtProps) {
  return (
    <Svg {...props} paints={["mint", "cream"]}>
      {(f, uid) => (
        <>
          <path
            d="M60 10 L100 24 V58 C100 84 82 102 60 112 C38 102 20 84 20 58 V24 Z"
            fill={f("mint")}
            stroke={f("mint")}
            strokeWidth="6"
            strokeLinejoin="round"
          />
          <path
            d="M42 60 l12 12 24 -26"
            fill="none"
            stroke={PALETTE.cream}
            strokeWidth="9"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <Shine uid={uid} cx={40} cy={34} rx={10} ry={6} />
        </>
      )}
    </Svg>
  );
}

export function TagArt(props: ArtProps) {
  return (
    <Svg {...props} paints={["peach", "cream"]}>
      {(f, uid) => (
        <>
          <path
            d="M58 12 H96 a12 12 0 0 1 12 12 V62 L60 110 a10 10 0 0 1 -14 0 L10 74 a10 10 0 0 1 0 -14 Z"
            fill={f("peach")}
            stroke={f("peach")}
            strokeWidth="6"
            strokeLinejoin="round"
          />
          <circle cx="86" cy="34" r="9" fill={f("cream")} />
          <Shine uid={uid} cx={64} cy={30} rx={12} ry={5} />
        </>
      )}
    </Svg>
  );
}

export function ClockArt(props: ArtProps) {
  return (
    <Svg {...props} paints={["sky", "cream", "terracotta"]}>
      {(f, uid) => (
        <>
          <circle cx="60" cy="62" r="46" fill={f("sky")} />
          <circle cx="60" cy="62" r="34" fill={f("cream")} />
          <path
            d="M60 62 V40"
            stroke={PALETTE.ink}
            strokeWidth="6"
            strokeLinecap="round"
          />
          <path
            d="M60 62 L76 72"
            stroke={f("terracotta")}
            strokeWidth="6"
            strokeLinecap="round"
          />
          <circle cx="60" cy="62" r="5" fill={PALETTE.ink} />
          <Shine uid={uid} cx={40} cy={34} rx={12} ry={6} />
        </>
      )}
    </Svg>
  );
}

export function MapPinArt(props: ArtProps) {
  return (
    <Svg {...props} paints={["terracotta", "cream", "mint"]}>
      {(f, uid) => (
        <>
          <ellipse cx="60" cy="106" rx="30" ry="8" fill={f("mint")} />
          <path
            d="M60 104 C60 104 22 66 22 44 a38 38 0 0 1 76 0 C98 66 60 104 60 104 Z"
            fill={f("terracotta")}
          />
          <circle cx="60" cy="44" r="15" fill={f("cream")} />
          <Shine uid={uid} cx={42} cy={26} rx={10} ry={6} />
        </>
      )}
    </Svg>
  );
}

// --- lookup -------------------------------------------------------------------

/**
 * The illustration for a service, by slug. Unknown slugs get the comb rather
 * than nothing, so a service the owner adds later still has a picture.
 */
const BY_SLUG: Record<string, (p: ArtProps) => React.ReactElement> = {
  "hair-cutting": ScissorsArt,
  shaving: RazorArt,
  "face-massage": FaceArt,
  "hair-spa": DropletArt,
  "beard-trim": BeardArt,
  "head-massage": StonesArt,
  "hair-colour": SwatchesArt,
  "hair-color": SwatchesArt,
  facial: JarArt,
};

export function ServiceArt({ slug, ...props }: ArtProps & { slug: string }) {
  const Art = BY_SLUG[slug] ?? CombArt;
  return <Art {...props} />;
}

/** Pastel tile behind each service, cycled so neighbours differ. */
const TILES = [
  "bg-peach",
  "bg-lavender",
  "bg-mint",
  "bg-sky",
  "bg-butter",
  "bg-rose",
] as const;

export function tileFor(index: number): (typeof TILES)[number] {
  return TILES[index % TILES.length];
}
