import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useRainGuard } from "../context/RainGuardContext";
import { formatGen } from "../lib/client";
import type { Stats } from "../lib/types";

const TICKER = [
  "RAIN",
  "HEAT",
  "COVERED",
  "NO CLAIM FORMS",
  "PUBLIC DATA",
  "AUTO-SETTLEMENT",
];

export default function Home() {
  const { contract } = useRainGuard();
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    contract
      .getStats()
      .then(setStats)
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Failed to load stats."),
      );
  }, [contract]);

  const tickerRow = [...TICKER, ...TICKER];

  return (
    <>
      <section className="hero">
        <div className="container">
          <span className="eyebrow">
            <span className="pulse" /> Live on GenLayer StudioNet
          </span>
          <h1>
            Weather coverage
            <br />
            <span className="grn">that pays itself out.</span>
          </h1>
          <p className="lede">
            No claim forms. No adjusters. An insurer funds a payout against a
            measurable trigger — rainfall under a threshold, a heatwave over
            one. When the window closes, GenLayer's validators read the
            Open-Meteo archive for that exact place and window, and the money
            moves on published data.
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
          <div className="stats-row">
            <div className="stat">
              <div className="stat-value">{stats?.total_policies ?? "—"}</div>
              <div className="stat-label">Policies on-chain</div>
            </div>
            <div className="stat">
              <div className="stat-value lime">{stats?.active ?? "—"}</div>
              <div className="stat-label">Coverage live</div>
            </div>
            <div className="stat">
              <div className="stat-value amber">
                {stats ? formatGen(stats.escrow_locked) : "—"}
              </div>
              <div className="stat-label">Held in escrow</div>
            </div>
            <div className="stat">
              <div className="stat-value">{stats?.paid ?? "—"}</div>
              <div className="stat-label">Paid out</div>
            </div>
          </div>
        </div>
      </section>

      <div className="marquee-strip" aria-hidden="true">
        <div className="marquee-track">
          {tickerRow.map((t, i) => (
            <span key={i} className="marquee-item">
              {t} <em>☔</em>
            </span>
          ))}
        </div>
      </div>

      <section className="section">
        <div className="container">
          <span className="section-kicker">The triggers</span>
          <h2 className="section-title">
            Rain. Heat. <span className="grn">Covered.</span>
          </h2>
          <div className="feature-grid">
            <div className="feature-card">
              <span className="feature-emoji">🌧</span>
              <h3>Rainfall triggers</h3>
              <p>
                A policy covers a place and a window against drought or flood —
                "less than 8mm of rain over Jakarta, Sept 4–7". The number
                decides, not a claim.
              </p>
            </div>
            <div className="feature-card">
              <span className="feature-emoji">🌡</span>
              <h3>Temperature triggers</h3>
              <p>
                Heatwave or cold snap — "max temperature above 33.5°C in
                Singapore". Same mechanics, different thermometer.
              </p>
            </div>
            <div className="feature-card">
              <span className="feature-emoji">⚡</span>
              <h3>Auto settlement</h3>
              <p>
                Anyone triggers it once the window closes. Two leaders fetch
                the same archive and must agree byte-for-byte. No oracle, no
                judge, no paperwork.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="section alt">
        <div className="container">
          <span className="section-kicker">What is RainGuard?</span>
          <h2 className="section-title">
            A policy that <span className="grn">reads the weather itself.</span>
          </h2>
          <p className="story muted">
            Before claims, before adjusters, before insurance paperwork — there
            was a number: how much it rained, how hot it got. RainGuard puts a
            payout behind that number. The insurer locks the payout in escrow,
            a buyer pays a premium for the coverage, and when the window closes
            the contract reads the public weather archive and settles. Trigger
            hit → the buyer is paid. Missed → the insurer keeps the pot.
          </p>
          <p className="tagline">🌍 Public data. Consensus math. No claim to file.</p>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="feature-grid two">
            <Link to="/policies" className="feature-card">
              <span className="feature-emoji">🛡️</span>
              <h3>Live coverage board</h3>
              <p>
                Real policies on-chain right now — buy coverage, or settle one
                the moment its window closes and the data lands.
              </p>
              <span className="arrow-link">Open the board →</span>
            </Link>
            <Link to="/create" className="feature-card">
              <span className="feature-emoji">🌦</span>
              <h3>Issue a policy</h3>
              <p>
                Put a payout behind a place, a window and a number. Lock it in
                escrow, let the trigger decide who walks away with the pot.
              </p>
              <span className="arrow-link">Issue a policy →</span>
            </Link>
          </div>
        </div>
      </section>

      <section className="cta-band">
        <div className="container">
          <h2 className="section-title">🔥 Live on GenLayer StudioNet</h2>
          <p className="muted">
            Two real policies are in the wild right now — they settle as their
            windows close. Watch the board, or fund the next one.
          </p>
          <Link to="/policies" className="btn">
            See the live board
          </Link>
        </div>
      </section>
    </>
  );
}