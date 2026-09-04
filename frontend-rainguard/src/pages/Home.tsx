import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useRainGuard } from "../context/RainGuardContext";
import { formatGen } from "../lib/client";
import type { Stats } from "../lib/types";

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
            <span className="grad">that pays itself out.</span>
          </h1>
          <p className="lede">
            No claim forms. No adjusters. An insurer funds a payout against a
            measurable trigger — rainfall under a threshold, a heatwave over
            one. When the window closes, GenLayer's validators read the
            Open-Meteo archive for that exact place and window, and the money
            moves on published data.
          </p>
          <div className="hero-cta">
            <Link to="/policies" className="primary">
              Browse coverage
            </Link>
            <Link to="/create" className="ghost">
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

      <section className="section">
        <div className="container">
          <h2 className="section-title">
            How a policy <span className="accent">settles</span>
          </h2>
          <div className="steps">
            <div className="step">
              <div className="step-n">STEP 01</div>
              <h3>An insurer funds the payout</h3>
              <p>
                They set the location, the date window, the trigger (rainfall
                below or above a threshold, temperature below or above one) and
                the premium a buyer pays. The payout sits in escrow.
              </p>
            </div>
            <div className="step">
              <div className="step-n">STEP 02</div>
              <h3>A buyer takes the coverage</h3>
              <p>
                Anyone who isn't the insurer pays the premium while the window
                is still open. Buying closes the moment the window ends — no
                taking coverage on an outcome that's already public.
              </p>
            </div>
            <div className="step">
              <div className="step-n">STEP 03</div>
              <h3>Validators read the archive</h3>
              <p>
                After the window closes, anyone triggers settlement. Two
                leaders fetch the same Open-Meteo data and must agree on the
                number byte-for-byte. Trigger hit → buyer is paid. Missed →
                insurer keeps the pot.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="section alt">
        <div className="container">
          <h2 className="section-title">
            Numbers, not opinions.{" "}
            <span className="accent">No AI judgment call.</span>
          </h2>
          <p className="muted" style={{ maxWidth: 740, marginBottom: 26 }}>
            The trigger is arithmetic on published weather history. Both
            leaders compute the same value from the same archive, so consensus
            is strict: outputs must match byte-for-byte. If the archive can't
            be read, the policy stays active for a retry, and if consensus
            never settles it within a week, both sides unwind — the premium
            goes back to the buyer, the payout to the insurer. No one profits
            from a network failure.
          </p>
          <div className="cta-band">
            <Link to="/create" className="primary">
              Put a payout behind the weather →
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}
