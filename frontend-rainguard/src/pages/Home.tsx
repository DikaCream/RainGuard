import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useRainGuard } from "../context/RainGuardContext";
import { formatGen } from "../lib/client";
import type { Policy, Stats } from "../lib/types";
import Radar from "../components/Radar";
import {
  BoltIcon,
  DropletIcon,
  RadarIcon,
  ShieldIcon,
  ThermometerIcon,
} from "../components/icons";
import { useTilt } from "../hooks/useTilt";

const TICKER = [
  "RAIN",
  "HEAT",
  "COVERED",
  "NO CLAIM FORMS",
  "PUBLIC DATA",
  "AUTO-SETTLEMENT",
];

/**
 * Double-decker ticker driven by requestAnimationFrame so it runs in every
 * environment (including OS reduced-motion settings that freeze CSS
 * animations). Each track holds the ticker twice and loops by wrapping the
 * offset at half the track width; the second row scrolls the other way.
 */
function TickerRow({ reverse = false }: { reverse?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let raf = 0;
    let x = 0;
    let last = performance.now();
    const speed = reverse ? 34 : 46; // px per second
    const step = (t: number) => {
      const dt = Math.min(t - last, 100);
      last = t;
      x += reverse ? (dt / 1000) * speed : -(dt / 1000) * speed;
      const half = el.scrollWidth / 2;
      if (half > 0) {
        if (x <= -half) x += half;
        if (x >= 0) x -= half;
      }
      el.style.transform = `translateX(${x}px)`;
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [reverse]);

  const tickerRow = [...TICKER, ...TICKER];
  return (
    <div className={`marquee-track ${reverse ? "rev" : ""}`} ref={ref}>
      {tickerRow.map((t, i) => (
        <span key={i} className="marquee-item">
          {t}
          <span className="mq-sep">
            <DropletIcon size={13} />
          </span>
        </span>
      ))}
    </div>
  );
}

function Ticker() {
  return (
    <div className="marquee-strip" aria-hidden="true">
      <TickerRow />
      <TickerRow reverse />
    </div>
  );
}

interface FeatureProps {
  icon: ReactNode;
  iconColor?: string;
  title: string;
  body: ReactNode;
  to?: string;
  arrow?: string;
}

function FeatureInner({ icon, iconColor, title, body, arrow }: FeatureProps) {
  return (
    <>
      <span
        className="fw"
        aria-hidden="true"
        style={iconColor ? { color: iconColor } : undefined}
      >
        {icon}
      </span>
      <span
        className="feature-emoji pop"
        style={iconColor ? { color: iconColor } : undefined}
      >
        {icon}
      </span>
      <h3>{title}</h3>
      <p>{body}</p>
      {arrow && <span className="arrow-link">{arrow}</span>}
    </>
  );
}

/** A mouse-tilted feature card with a cursor-following glare. */
function Feature(props: FeatureProps) {
  const tiltDiv = useTilt<HTMLDivElement>({ max: 9 });
  const tiltLink = useTilt<HTMLAnchorElement>({ max: 9 });
  if (props.to) {
    return (
      <Link to={props.to} className="feature-card tilt glare" {...tiltLink}>
        <FeatureInner {...props} />
      </Link>
    );
  }
  return (
    <div className="feature-card tilt glare" {...tiltDiv}>
      <FeatureInner {...props} />
    </div>
  );
}

export default function Home() {
  const { contract } = useRainGuard();
  const [stats, setStats] = useState<Stats | null>(null);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([contract.getStats(), contract.listPolicies(0, 8)])
      .then(([s, p]) => {
        setStats(s);
        setPolicies(p);
      })
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Failed to load stats."),
      );
  }, [contract]);

  return (
    <>
      <section className="hero">
        <div className="container hero-grid">
          <div>
            <span className="eyebrow">
              <span className="pulse" /> Live on GenLayer StudioNet
            </span>
            <h1>
              Weather coverage
              <br />
              <span className="text-outline">that pays</span>
              <br />
              <span className="text-grad">itself out.</span>
            </h1>
            <p className="lede">
              No claim forms, no adjusters. An insurer funds a payout against a
              measurable trigger, rain under a threshold or a heatwave over
              one. When the window closes, validators read the Open-Meteo
              archive for that place and the money moves on published data.
            </p>
            <div className="hero-cta">
              <Link to="/policies" className="btn">
                Browse coverage
              </Link>
              <Link to="/create" className="btn ghost">
                Issue a policy
              </Link>
            </div>
            {error && <div className="error-banner">{error}</div>}
            <div className="mini-stats">
              <div className="mini-stat">
                <span className="mini-stat-value">{stats?.total_policies ?? "–"}</span>
                <span className="mini-stat-label">policies on-chain</span>
              </div>
              <div className="mini-stat">
                <span className="mini-stat-value lime">{stats?.active ?? "–"}</span>
                <span className="mini-stat-label">coverage live</span>
              </div>
              <div className="mini-stat">
                <span className="mini-stat-value amber">
                  {stats ? formatGen(stats.escrow_locked) : "–"}
                </span>
                <span className="mini-stat-label">in escrow</span>
              </div>
              <div className="mini-stat">
                <span className="mini-stat-value">{stats?.paid ?? "–"}</span>
                <span className="mini-stat-label">paid out</span>
              </div>
            </div>
          </div>

          <div className="hero-visual">
            <Radar policies={policies} stats={stats} />
            {stats && (
              <>
                <span className="float-chip fc-live" aria-hidden="true">
                  <span className="pulse" /> {stats.active} ACTIVE
                </span>
                <span className="float-chip fc-escrow" aria-hidden="true">
                  {formatGen(stats.escrow_locked)} ESCROW
                </span>
                <span className="float-chip fc-paid" aria-hidden="true">
                  {stats.paid} PAID OUT
                </span>
              </>
            )}
          </div>
        </div>
      </section>

      <Ticker />

      <section className="section">
        <div className="container" data-reveal>
          <span className="section-kicker">01 / The triggers</span>
          <h2 className="section-title">
            Rain. Heat. <span className="text-outline-sm">Covered.</span>
          </h2>
          <div className="feature-grid">
            <Feature
              icon={<DropletIcon size={26} />}
              title="Rainfall triggers"
              body={
                <>
                  Drought cover or flood cover, one place and one window. It
                  pays when total rain lands{" "}
                  <em>under 8mm over Jakarta, Sep 4–7</em>; the number decides.
                </>
              }
            />
            <Feature
              icon={<ThermometerIcon size={26} />}
              iconColor="var(--violet)"
              title="Temperature triggers"
              body={
                <>
                  Max daily temperature{" "}
                  <em>above 33.5°C in Singapore</em> is a heatwave; under some
                  floor it's a cold snap. Same contract, whichever side of the
                  number you cover.
                </>
              }
            />
            <Feature
              icon={<BoltIcon size={26} />}
              iconColor="var(--sun)"
              title="Auto settlement"
              body={
                <>
                  Anyone can settle once the window closes. Two leaders fetch
                  the same archive and must match byte-for-byte, so there's no
                  judge and no oracle to argue with.
                </>
              }
            />
          </div>
        </div>
      </section>

      <section className="section alt angle">
        <div className="container" data-reveal>
          <span className="section-kicker">02 / What is RainGuard?</span>
          <h2 className="section-title">
            A policy that{" "}
            <span className="text-grad">reads the weather itself.</span>
          </h2>            <p className="story muted">
              Before claims, before adjusters, before insurance paperwork, there
              was a number: how much it rained, how hot it got. RainGuard puts a
              payout behind that number. The insurer locks it in escrow, a
              buyer pays a premium for the coverage, and when the window closes
              the contract reads the public weather archive and settles.{" "}
              <span className="story-outcome">
                Trigger hit, the buyer is paid. Missed, the insurer keeps the
                pot.
              </span>
            </p>
          <p className="tagline">
            <ShieldIcon size={18} /> The archive decides. The contract pays.
          </p>
        </div>
      </section>

      <section className="section">
        <div className="container" data-reveal>
          <span className="section-kicker">03 / Where to go next</span>
          <div className="feature-grid two">
            <Feature
              to="/policies"
              arrow="Open the board"
              icon={<RadarIcon size={26} />}
              title="Live coverage board"
              body={
                <>
                  Real policies on-chain right now, plotted by location. Buy
                  coverage, or settle one the moment its window closes.
                </>
              }
            />
            <Feature
              to="/create"
              arrow="Issue a policy"
              icon={<ThermometerIcon size={26} />}
              iconColor="var(--violet)"
              title="Issue a policy"
              body={
                <>
                  Put a payout behind a place, a window and a number. Lock it
                  in escrow, let the trigger decide who walks away with the
                  pot.
                </>
              }
            />
          </div>
        </div>
      </section>

      <section className="cta-band" data-reveal>
        <div className="container">
          <h2 className="section-title">
            <RadarIcon size={30} /> 04 / Live on GenLayer StudioNet
          </h2>
          <p className="muted">
            Real policies are in the wild right now and settle as their windows
            close. Watch the board, or fund the next one.
          </p>
          <Link to="/policies" className="btn">
            See the live board
          </Link>
        </div>
      </section>
    </>
  );
}