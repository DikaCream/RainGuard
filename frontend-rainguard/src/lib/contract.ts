import { CONTRACT_ADDRESS } from "../config";
import { Config, Policy, Stats, toBigInt, toInt } from "./types";
import { withReadRetry } from "./errors";
import { CalldataAddress } from "genlayer-js/types";

/** Wrap a 0x-address into the CalldataAddress wrapper genlayer-js expects. */
function toCalldataAddress(address: string): CalldataAddress {
  const hex = address.startsWith("0x") ? address.slice(2) : address;
  const bytes = new Uint8Array(
    hex.match(/.{2}/g)!.map((h) => parseInt(h, 16)),
  );
  return new CalldataAddress(bytes);
}

function fromMapLike(v: any): Record<string, any> {
  if (v instanceof Map) {
    const out: Record<string, any> = {};
    v.forEach((val: any, key: any) => {
      out[String(key)] = val;
    });
    return out;
  }
  return (v ?? {}) as Record<string, any>;
}

function toPolicy(v: any): Policy {
  const o = fromMapLike(v);
  return {
    id: toInt(o.id),
    insurer: String(o.insurer ?? ""),
    buyer: String(o.buyer ?? ""),
    bought: Boolean(o.bought ?? false),
    metric: String(o.metric ?? "rainfall") as Policy["metric"],
    lat: String(o.lat ?? ""),
    lon: String(o.lon ?? ""),
    start_date: String(o.start_date ?? ""),
    end_date: String(o.end_date ?? ""),
    threshold: String(o.threshold ?? ""),
    condition: String(o.condition ?? "below") as Policy["condition"],
    premium: toBigInt(o.premium),
    payout: toBigInt(o.payout),
    status: String(o.status ?? "OPEN") as Policy["status"],
    measured: String(o.measured ?? ""),
    attempts: toInt(o.attempts),
    last_settled_at: toInt(o.last_settled_at),
    created_at: toInt(o.created_at),
    bought_at: toInt(o.bought_at),
    settle_eligible_at: toInt(o.settle_eligible_at),
    stale_at: toInt(o.stale_at),
  };
}

function toConfig(v: any): Config {
  const o = fromMapLike(v);
  return {
    policy_count: toInt(o.policy_count),
    escrow_locked: toBigInt(o.escrow_locked),
    metrics: Array.isArray(o.metrics) ? (o.metrics as Config["metrics"]) : ["rainfall", "temperature"],
    conditions: Array.isArray(o.conditions) ? (o.conditions as Config["conditions"]) : ["below", "above"],
    max_window_days: toInt(o.max_window_days),
    max_payout_gen: toInt(o.max_payout_gen),
    settle_after_end_seconds: toInt(o.settle_after_end_seconds),
    max_settle_attempts: toInt(o.max_settle_attempts),
  };
}

function toStats(v: any): Stats {
  const o = fromMapLike(v);
  return {
    total_policies: toInt(o.total_policies),
    open: toInt(o.open),
    active: toInt(o.active),
    paid: toInt(o.paid),
    expired: toInt(o.expired),
    cancelled: toInt(o.cancelled),
    refunded: toInt(o.refunded),
    escrow_locked: toBigInt(o.escrow_locked),
  };
}

/**
 * Typed wrapper over the deployed RainGuard contract.
 * Read methods work without an account; write methods sign via the client.
 */
export class RainGuard {
  constructor(private client: any, private address: string = CONTRACT_ADDRESS) {}

  private async read(functionName: string, args: unknown[] = []): Promise<any> {
    return withReadRetry(() =>
      this.client.readContract({
        address: this.address as `0x${string}`,
        functionName,
        args,
      }),
    );
  }

  private async write(
    functionName: string,
    args: unknown[],
    value: bigint = 0n,
  ): Promise<string> {
    const txHash = await this.client.writeContract({
      address: this.address as `0x${string}`,
      functionName,
      args,
      value,
    });
    return txHash as string;
  }

  async waitForReceipt(txHash: string, retries = 50, interval = 3000): Promise<any> {
    return this.client.waitForTransactionReceipt({
      hash: txHash,
      status: "ACCEPTED" as any,
      retries,
      interval,
    });
  }

  // ---- reads ----------------------------------------------------------
  async getConfig(): Promise<Config> {
    return toConfig(await this.read("get_config"));
  }

  async getStats(): Promise<Stats> {
    return toStats(await this.read("get_stats"));
  }

  async getPolicy(id: number): Promise<Policy | null> {
    const v = await this.read("get_policy", [id]);
    if (v == null) return null;
    return toPolicy(v);
  }

  async listPolicies(offset = 0, limit = 50): Promise<Policy[]> {
    const v = await this.read("list_policies", [offset, limit]);
    return Array.isArray(v) ? v.map(toPolicy) : [];
  }

  async listInsurerPolicies(insurer: string, offset = 0, limit = 50): Promise<Policy[]> {
    const v = await this.read("list_insurer_policies", [
      toCalldataAddress(insurer),
      offset,
      limit,
    ]);
    return Array.isArray(v) ? v.map(toPolicy) : [];
  }

  async listBuyerPolicies(buyer: string, offset = 0, limit = 50): Promise<Policy[]> {
    const v = await this.read("list_buyer_policies", [
      toCalldataAddress(buyer),
      offset,
      limit,
    ]);
    return Array.isArray(v) ? v.map(toPolicy) : [];
  }

  // ---- writes ---------------------------------------------------------
  /** Insurer creates coverage and locks the payout (sent as value). */
  async createPolicy(
    metric: string,
    lat: string,
    lon: string,
    startDate: string,
    endDate: string,
    threshold: string,
    condition: string,
    premiumWei: bigint,
    payoutWei: bigint,
  ): Promise<string> {
    return this.write(
      "create_policy",
      [metric, lat, lon, startDate, endDate, threshold, condition, premiumWei, payoutWei],
      payoutWei,
    );
  }

  /** Buyer pays the premium (sent as value) and takes the coverage. */
  async buyPolicy(policyId: number, premiumWei: bigint): Promise<string> {
    return this.write("buy_policy", [policyId], premiumWei);
  }

  /** Insurer backs out while the policy is still OPEN. */
  async cancelPolicy(policyId: number): Promise<string> {
    return this.write("cancel_policy", [policyId]);
  }

  /** Permissionless once the window ends; runs validator consensus. */
  async settlePolicy(policyId: number): Promise<string> {
    return this.write("settle_policy", [policyId]);
  }

  /** Fail closed after the stale window; unwinds both sides. */
  async closeStalePolicy(policyId: number): Promise<string> {
    return this.write("close_stale_policy", [policyId]);
  }
}
