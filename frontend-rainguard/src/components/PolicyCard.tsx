import type { Policy } from "../lib/types";
import { formatAddress, formatGen } from "../lib/client";
import Countdown from "./Countdown";
import { MetricBadge, StatusBadge } from "./StatusBadge";
import { DropletIcon, ThermometerIcon } from "./icons";
import { useTilt } from "../hooks/useTilt";

interface PolicyCardProps {
  policy: Policy;
  me: string | null;
  busy: boolean;
  now: number; // unix seconds
  onBuy: (policy: Policy) => void;
  onCancel: (policy: Policy) => void;
  onSettle: (policy: Policy) => void;
  onCloseStale: (policy: Policy) => void;
}

/** Unix ts when buying closes: end of end_date's day (midnight after it). */
export function buyClosesAt(p: Policy): number {
  const [y, m, d] = p.end_date.split("-").map(Number);
  const dayStart = Date.UTC(y, m - 1, d) / 1000;
  return dayStart + 86400;
}

/** Human-readable trigger, e.g. "rainfall under 30mm over the window". */
export function describeTrigger(p: Policy): string {
  const unit = p.metric === "rainfall" ? "mm" : "°C";
  const dir = p.condition === "below" ? "below" : "above";
  const what =
    p.metric === "rainfall"
      ? p.condition === "below"
        ? "drier than"
        : "wetter than"
      : p.condition === "below"
        ? "cooler than"
        : "hotter than";
  return `${what} ${p.threshold}${unit} ${dir}`;
}

export function describeLocation(p: Policy): string {
  return `${p.lat}, ${p.lon}`;
}

export default function PolicyCard({
  policy: p,
  me,
  busy,
  now,
  onBuy,
  onCancel,
  onSettle,
  onCloseStale,
}: PolicyCardProps) {
  const tilt = useTilt<HTMLElement>({ max: 4 });
  const isInsurer = !!me && me.toLowerCase() === p.insurer.toLowerCase();
  const isBuyer = !!me && p.buyer && me.toLowerCase() === p.buyer.toLowerCase();
  const canSettle = p.status === "ACTIVE" && now >= p.settle_eligible_at;
  const canCloseStale = p.status === "ACTIVE" && now >= p.stale_at;
  const windowLabel =
    p.start_date === p.end_date
      ? p.end_date
      : `${p.start_date} → ${p.end_date}`;

  const coordsLabel = `(${describeLocation(p)})`;

  return (
    <article
      className={`card policy-card tilt glare pc-${p.status.toLowerCase()}`}
      {...tilt}
    >
      <div className="row pc-head">
        <span className="pc-emoji pop">
          {p.metric === "rainfall" ? (
            <DropletIcon size={22} />
          ) : (
            <ThermometerIcon size={22} />
          )}
        </span>
        <span className="pc-id mono">POLICY #{p.id}</span>
        <StatusBadge status={p.status} />
      </div>

      <MetricBadge metric={p.metric} />

      <h3 className="pc-trigger">
        {p.metric === "rainfall" ? "Rainfall" : "Max temperature"}{" "}
        {p.condition === "below" ? "below" : "above"} {p.threshold}
        {p.metric === "rainfall" ? " mm" : " °C"}
      </h3>

      <p className="pc-desc muted">
        Coverage for <strong>{windowLabel}</strong> at {coordsLabel}. If the
        daily archive confirms the trigger across the window, the buyer is paid
        the full payout; otherwise the insurer keeps the pot.
      </p>

      <div className="pc-window">
        <span className="pc-window-label">Window</span>
        <span className="mono">{windowLabel}</span>
      </div>

      <div className="pc-money">
        <div className="pc-money-col">
          <span className="pc-money-label">Premium</span>
          <span className="pc-premium">{formatGen(p.premium)}</span>
        </div>
        <div className="pc-money-col">
          <span className="pc-money-label">Payout</span>
          <span className="pc-payout">{formatGen(p.payout)}</span>
        </div>
        <div className="pc-money-col">
          <span className="pc-money-label">At risk</span>
          <span className="pc-risk">
            {formatGen(p.payout + (p.bought ? p.premium : 0n))}
          </span>
        </div>
      </div>

      <div className="row pc-parties">
        {p.bought ? (
          <>
            <span className="muted" style={{ fontSize: "0.8rem" }}>
              Insurer: {isInsurer ? "you" : formatAddress(p.insurer)}
            </span>
            <span className="muted" style={{ fontSize: "0.8rem" }}>
              Buyer: {isBuyer ? "you" : formatAddress(p.buyer)}
            </span>
          </>
        ) : (
          <span className="muted" style={{ fontSize: "0.8rem" }}>
            Insurer: {isInsurer ? "you" : formatAddress(p.insurer)}
          </span>
        )}
      </div>

      {p.status === "PAID" && (
        <div className="pc-outcome outcome-paid">
          Measured {p.measured}
          {p.metric === "rainfall" ? " mm" : " °C"}. Trigger hit, buyer paid.
        </div>
      )}
      {p.status === "EXPIRED" && (
        <div className="pc-outcome outcome-expired">
          Measured {p.measured}
          {p.metric === "rainfall" ? " mm" : " °C"}. Trigger missed, insurer
          keeps the pot.
        </div>
      )}
      {p.status === "REFUNDED" && (
        <div className="pc-outcome outcome-refunded">
          Never settled. Premium back to buyer, payout back to insurer.
        </div>
      )}

      <div className="row">
        {p.status === "OPEN" && (
          <Countdown
            target={buyClosesAt(p)}
            prefix="Buying closes in"
            passed="Buying closed"
          />
        )}
        {p.status === "ACTIVE" && !canSettle && (
          <Countdown target={p.settle_eligible_at} prefix="Settles in" />
        )}
        {p.status === "ACTIVE" && canSettle && !canCloseStale && (
          <Countdown
            target={p.stale_at}
            prefix="Stale in"
            passed="Settlement open"
          />
        )}
      </div>

      <div className="row pc-actions">
        {p.status === "OPEN" && isInsurer && (
          <button
            className="ghost small"
            disabled={busy}
            onClick={() => onCancel(p)}
          >
            Cancel policy
          </button>
        )}
        {p.status === "OPEN" && !isInsurer && (
          <button
            className="primary"
            disabled={busy || !me}
            onClick={() => onBuy(p)}
          >
            Buy coverage · {formatGen(p.premium)}
          </button>
        )}
        {p.status === "OPEN" && !isInsurer && !me && (
          <span className="muted" style={{ fontSize: "0.85rem" }}>
            Connect a wallet to buy coverage
          </span>
        )}
        {canSettle && (
          <button
            className="primary"
            disabled={busy}
            onClick={() => onSettle(p)}
          >
            Settle (validators check the data)
          </button>
        )}
        {canSettle && canCloseStale && (
          <button
            className="ghost small"
            disabled={busy}
            onClick={() => onCloseStale(p)}
            title="Consensus never settled: unwind both sides"
          >
            Close stale (unwind)
          </button>
        )}
      </div>
    </article>
  );
}
