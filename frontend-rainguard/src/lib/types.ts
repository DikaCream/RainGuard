/**
 * Types mirroring the RainGuard contract state.
 *
 * Premium and payout amounts are stored on-chain in wei and returned by the
 * node as number, bigint or string depending on magnitude; every helper
 * normalizes them to bigint. Small ints (ids, timestamps) are normalized to
 * number.
 */

export type PolicyStatus =
  | "OPEN"
  | "ACTIVE"
  | "PAID"
  | "EXPIRED"
  | "CANCELLED"
  | "REFUNDED";
export type Metric = "rainfall" | "temperature";
export type Condition = "below" | "above";

export interface Policy {
  id: number;
  insurer: string;
  buyer: string; // "" until someone buys
  bought: boolean;
  metric: Metric;
  lat: string;
  lon: string;
  start_date: string; // ISO YYYY-MM-DD
  end_date: string;
  threshold: string; // decimal: mm for rainfall, degC for temperature
  condition: Condition;
  premium: bigint; // wei
  payout: bigint; // wei
  status: PolicyStatus;
  measured: string; // value validators computed once settled, "" while open
  attempts: number;
  last_settled_at: number;
  created_at: number;
  bought_at: number;
  settle_eligible_at: number; // unix seconds
  stale_at: number; // settle_eligible_at + stale window
}

export interface Config {
  policy_count: number;
  escrow_locked: bigint; // wei
  metrics: Metric[];
  conditions: Condition[];
  max_window_days: number;
  max_payout_gen: number;
  settle_after_end_seconds: number;
  max_settle_attempts: number;
}

export interface Stats {
  total_policies: number;
  open: number;
  active: number;
  paid: number;
  expired: number;
  cancelled: number;
  refunded: number;
  escrow_locked: bigint; // wei
}

export function toInt(v: unknown): number {
  if (typeof v === "number") return v;
  if (typeof v === "bigint") return Number(v);
  if (typeof v === "string") return Number(v);
  return 0;
}

export function toBigInt(v: unknown): bigint {
  if (typeof v === "bigint") return v;
  if (typeof v === "number") return BigInt(Math.round(v));
  if (typeof v === "string") return BigInt(v);
  return 0n;
}
