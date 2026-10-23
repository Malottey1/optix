// #/ Home: what Optix is in one screen. The hero is the audited, cleaned line-up artwork
// (docs/brand-audit.md); its top half is plain colour bands, so the text sits on a dark panel
// there (on phones, below the picture), never directly on a bright band. Every number on this page
// is read from ui.json's verification ledger, nothing is typed in.
import { Link } from "react-router";
import { TeamBadge } from "../../components/brand/TeamBadge";
import { Icon } from "../../components/icons";
import { useData } from "../../data/context";
import { num } from "../../lib/format";
import { useT, type Key } from "../../lib/i18n";

/** Club order of the hero artwork, left to right. */
const ORDER = ["AUR", "NTG", "CAL", "VES", "HAR"];

const cta =
  "inline-flex h-11 items-center justify-center gap-2 rounded-full px-5 text-[14.5px] font-bold transition-[filter,border-color,color] duration-150";

function Hero() {
  const { t } = useT();
  return (
    <section
      aria-labelledby="home-title"
      className="relative overflow-hidden rounded-2xl border border-line bg-surface-1 elev-1"
    >
      <div className="relative lg:h-[clamp(500px,64vh,640px)]">
        <img
          src="./brand/hero-lineup-1600.webp"
          srcSet="./brand/hero-lineup-800.webp 800w, ./brand/hero-lineup-1600.webp 1600w"
          sizes="(min-width: 1680px) 1632px, calc(100vw - 48px)"
          width={1600}
          height={1200}
          alt={t("home_hero_alt")}
          fetchPriority="high"
          decoding="async"
          data-hero
          className="block aspect-[4/3] w-full object-cover object-[50%_30%] lg:absolute lg:inset-0 lg:aspect-auto lg:h-full"
        />
        {/* Large screens: a dark gradient over the top-left bands, then the text panel on it. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 hidden bg-[linear-gradient(100deg,rgba(5,8,15,0.92)_0%,rgba(5,8,15,0.78)_38%,rgba(5,8,15,0)_62%)] lg:block"
        />
        <div
          data-hero-panel
          className="relative px-5 pb-6 pt-5 sm:px-7 lg:absolute lg:left-0 lg:top-0 lg:max-w-[38rem] lg:px-10 lg:pt-10"
        >
          <h1
            id="home-title"
            data-hero-text
            className="text-balance text-[30px] font-bold leading-[1.08] tracking-tight text-ink sm:text-[38px] lg:text-[46px]"
          >
            {t("home_headline")}
          </h1>
          <p data-hero-text className="mt-4 max-w-[34rem] text-[15.5px] leading-relaxed text-ink-2 sm:text-[17px]">
            {t("home_sub")}
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link to="/live" className={`${cta} bg-accent text-accent-ink hover:brightness-110`}>
              <Icon name="live" className="h-[18px] w-[18px]" />
              {t("home_cta_live")}
            </Link>
            <Link
              to="/tech"
              className={`${cta} border border-line-strong bg-bg/80 text-ink hover:border-accent-line hover:text-accent`}
            >
              <Icon name="shield" className="h-[18px] w-[18px]" />
              {t("home_cta_tech")}
            </Link>
          </div>
        </div>
      </div>
      <p className="border-t border-line px-5 py-2.5 text-[12px] text-ink-3 sm:px-7" data-hero-caption>
        {t("home_caption")}
      </p>
    </section>
  );
}

function Clubs() {
  const m = useData();
  const { t } = useT();
  const teams = [...m.ui.teams.teams].sort((a, b) => ORDER.indexOf(a.code) - ORDER.indexOf(b.code));
  return (
    <section aria-labelledby="home-clubs" className="rounded-2xl border border-line bg-surface-1 pad elev-1">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="home-clubs" className="text-[16px] font-semibold text-ink">
          {t("home_clubs")}
        </h2>
        <Link
          to="/teams"
          className="inline-flex items-center gap-1 text-[13px] font-semibold text-accent hover:underline"
        >
          {t("home_clubs_link")}
          <Icon name="arrow" className="h-4 w-4" />
        </Link>
      </div>
      <ul className="mt-4 grid grid-cols-1 gap-2 min-[430px]:grid-cols-2 md:grid-cols-5">
        {teams.map((tm) => (
          <li key={tm.code}>
            <Link
              to="/teams"
              data-team={tm.code}
              className="flex items-center gap-3 rounded-xl border border-line bg-surface-2 px-3 py-2.5 hover:border-line-strong"
            >
              <TeamBadge code={tm.code} size={48} named />
              <span className="min-w-0">
                <span className="block truncate text-[14px] font-semibold text-ink">{tm.name}</span>
                <span className="block text-[12px] font-semibold tracking-[0.08em] text-ink-3">{tm.code}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

/* Small line illustrations in the app's own colours (no stock art, no digits). */
function ArtFacts() {
  return (
    <svg viewBox="0 0 120 64" aria-hidden="true" className="h-16 w-[120px]">
      {[10, 22, 34, 46].map((y, i) => (
        <g key={y}>
          <rect x="6" y={y - 4} width={[30, 22, 34, 18][i]} height="7" rx="2" fill="var(--surface-4)" />
          <rect x="6" y={y - 4} width={[18, 14, 26, 10][i]} height="7" rx="2" fill="var(--accent)" opacity="0.85" />
        </g>
      ))}
      <path
        d="M50 32h16m-5-5 5 5-5 5"
        fill="none"
        stroke="var(--ink-3)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <rect x="74" y="14" width="40" height="36" rx="8" fill="var(--surface-3)" stroke="var(--line-strong)" />
      {[24, 32, 40].map((y, i) => (
        <rect
          key={y}
          x="81"
          y={y - 2}
          width={[26, 20, 23][i]}
          height="4"
          rx="2"
          fill="var(--ink-2)"
          opacity={1 - i * 0.2}
        />
      ))}
    </svg>
  );
}

function ArtEvidence() {
  const dots: [number, number][] = [
    [14, 48],
    [30, 22],
    [48, 40],
    [64, 16],
  ];
  return (
    <svg viewBox="0 0 120 64" aria-hidden="true" className="h-16 w-[120px]">
      <rect x="78" y="10" width="36" height="44" rx="8" fill="var(--surface-3)" stroke="var(--accent-line)" />
      <path
        d="M88 32l5 5 10-11"
        fill="none"
        stroke="var(--pass)"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {dots.map(([x, y]) => (
        <line
          key={x}
          x1={x}
          y1={y}
          x2="78"
          y2="32"
          stroke="var(--line-strong)"
          strokeWidth="1.4"
          strokeDasharray="3 3"
        />
      ))}
      {dots.map(([x, y]) => (
        <circle
          key={`c${x}`}
          cx={x}
          cy={y}
          r="5"
          fill="var(--surface-1)"
          stroke="var(--muted-accent)"
          strokeWidth="2"
        />
      ))}
    </svg>
  );
}

function ArtTranslate() {
  // Three languages, the same highlighted number slot in each; labels at 11 px so they stay legible.
  return (
    <svg viewBox="0 0 132 64" aria-hidden="true" className="h-16 w-[132px]">
      {[0, 22, 44].map((y, i) => (
        <g key={y}>
          <rect x="0" y={y} width="132" height="19" rx="9.5" fill="var(--surface-3)" />
          <text x="8" y={y + 13.5} fontSize="11" fontWeight="700" fill="var(--ink-3)" fontFamily="var(--font-sans)">
            {["EN", "ES", "FR"][i]}
          </text>
          <rect x="32" y={y + 7.5} width={[30, 40, 35][i]} height="4" rx="2" fill="var(--ink-3)" opacity="0.55" />
          <rect x={[68, 78, 73][i]} y={y + 4.5} width="24" height="10" rx="3" fill="var(--accent)" />
        </g>
      ))}
    </svg>
  );
}

const FEATURES: { art: () => React.JSX.Element; title: Key; body: Key }[] = [
  { art: ArtFacts, title: "home_f1_title", body: "home_f1_body" },
  { art: ArtEvidence, title: "home_f2_title", body: "home_f2_body" },
  { art: ArtTranslate, title: "home_f3_title", body: "home_f3_body" },
];

function Features() {
  const { t } = useT();
  return (
    <section aria-labelledby="home-features">
      <h2 id="home-features" className="sr-only">
        {t("home_features")}
      </h2>
      <ul className="grid grid-cols-1 gap-flow md:grid-cols-3">
        {FEATURES.map(({ art: Art, title, body }) => (
          <li key={title} className="flex flex-col gap-3 rounded-2xl border border-line bg-surface-1 pad elev-1">
            <Art />
            <h3 className="text-[17px] font-bold tracking-tight text-ink">{t(title)}</h3>
            <p className="text-[14px] leading-relaxed text-ink-2">{t(body)}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Proof() {
  const m = useData();
  const { t, lang } = useT();
  const L = m.ui.ledger;
  const stats: { key: string; value: number; label: Key }[] = [
    { key: "attempts", value: L.attempts, label: "home_proof_attempts" },
    { key: "revised", value: L.counts.revised, label: "home_proof_revised" },
    { key: "published", value: L.total, label: "home_proof_published" },
  ];
  return (
    <section aria-labelledby="home-proof" className="rounded-2xl border border-line bg-surface-1 pad elev-1">
      <h2 id="home-proof" className="eyebrow">
        {t("home_proof")}
      </h2>
      <dl className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {stats.map((s) => (
          <div key={s.key} data-proof={s.key} className="flex flex-col-reverse rounded-xl bg-surface-2 px-4 py-3">
            <dt className="mt-1.5 text-[13px] text-ink-2">{t(s.label)}</dt>
            <dd className="display text-[40px] font-bold leading-none text-ink">{num(s.value, lang)}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

export default function HomePage() {
  return (
    <div className="flex flex-col gap-flow" data-page="home">
      <Hero />
      <Proof />
      <Features />
      <Clubs />
    </div>
  );
}
