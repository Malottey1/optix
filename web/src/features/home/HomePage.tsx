// #/ Home: what Optix is in one screen. The hero is the audited, cleaned line-up artwork
// (docs/brand-audit.md); its top half is plain colour bands, so the text sits on a dark panel
// there (on phones, below the picture), never directly on a bright band. Below the hero
// (HomeSections, lazy): the showcase strip, key insights, tiles, spotlight, patterns, teams and the
// trust strip; every number there is read from the data, nothing is typed in.
import { lazy, Suspense } from "react";
import { Link } from "react-router";
import { Icon } from "../../icons";
import { useT } from "../../lib/i18n";

// below the fold: its own chunk, and the showcase match file loads only there
const HomeSections = lazy(() => import("./HomeSections"));

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
              <Icon name="live" size={18} />
              {t("home_cta_live")}
            </Link>
            <Link
              to="/tech"
              className={`${cta} border border-line-strong bg-bg/80 text-ink hover:border-accent-line hover:text-accent`}
            >
              <Icon name="verdict-passed" size={18} />
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

export default function HomePage() {
  return (
    <div className="flex flex-col gap-flow" data-page="home">
      <Hero />
      <Suspense fallback={<div className="h-[640px] animate-pulse rounded-2xl bg-surface-2" />}>
        <HomeSections />
      </Suspense>
    </div>
  );
}
