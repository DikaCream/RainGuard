import { useCallback, useEffect, useMemo, useState } from "react";
import PolicyCard from "../components/PolicyCard";
import { useRainGuard } from "../context/RainGuardContext";
import type { Policy, Stats } from "../lib/types";
import { formatGen } from "../lib/client";

const POLL_MS = 10000;
// OPEN and ACTIVE are the live market; terminal statuses have no actions.
const ACTIVE_STATUSES = new Set(["OPEN", "ACTIVE"]);
type Filter = "active" | "all";

export default function Policies() {
  const { wallet, contract } = useRainGuard();
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [myPolicies, setMyPolicies] = useState<Policy[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [now, setNow] = useState(() => Math.floor(Date.now() / 1000));
  const [filter, setFilter] = useState<Filter>("active");

  const refresh = useCallback(async () => {
    try {
      const [all, s, mine] = await Promise.all([
        contract.listPolicies(0, 50),
        contract.getStats(),
        wallet.address
          ? Promise.all([
              contract.listInsurerPolicies(wallet.address, 0, 50),
              contract.listBuyerPolicies(wallet.address, 0, 50),
            ])
          : Promise.resolve([[], []]),
      ]);
      setPolicies(all);
      setStats(s);
      setMyPolicies([...mine[0], ...mine[1]]);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load policies.");
    } finally {
      setLoading(false);
    }
  }, [contract, wallet.address]);

  // Initial load + polling + a tick that flips countdowns every second.
  useEffect(() => {
    refresh();
    const poll = setInterval(refresh, POLL_MS);
    const clock = setInterval(() => setNow(Math.floor(Date.now() / 1000)), 1000);
    return () => {
      clearInterval(poll);
      clearInterval(clock);
    };
  }, [refresh]);

  const runTx = useCallback(
    async (id: number, fn: () => Promise<string>) => {
      setBusyId(id);
      setError(null);
      try {
        const txHash = await fn();
        await contract.waitForReceipt(txHash);
        await refresh();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Transaction failed.");
      } finally {
        setBusyId(null);
      }
    },
    [contract, refresh],
  );

  const actions = useMemo(
    () => ({
      onBuy: (p: Policy) => runTx(p.id, () => contract.buyPolicy(p.id, p.premium)),
      onCancel: (p: Policy) => runTx(p.id, () => contract.cancelPolicy(p.id)),
      onSettle: (p: Policy) => runTx(p.id, () => contract.settlePolicy(p.id)),
      onCloseStale: (p: Policy) =>
        runTx(p.id, () => contract.closeStalePolicy(p.id)),
    }),
    [contract, runTx],
  );

  const myPolicyIds = useMemo(() => new Set(myPolicies.map((p) => p.id)), [myPolicies]);
  const otherPolicies = policies.filter((p) => !myPolicyIds.has(p.id));

  const applyFilter = useCallback(
    (list: Policy[]) =>
      filter === "active" ? list.filter((p) => ACTIVE_STATUSES.has(p.status)) : list,
    [filter],
  );
  const visibleMy = useMemo(() => applyFilter(myPolicies), [applyFilter, myPolicies]);
  const visibleOther = useMemo(
    () => applyFilter(otherPolicies),
    [applyFilter, otherPolicies],
  );

  return (
    <div className="page container">
      <div className="page-head">
        <h1>Coverage on the market</h1>
        <p className="muted">
          Insurers fund a payout against a weather trigger; buyers pay the
          premium to take coverage. Take an <strong>OPEN</strong> policy by
          paying its premium, or settle an <strong>ACTIVE</strong> one once the
          window has ended — the validators check the archive and the money
          moves itself.
        </p>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {stats && (
        <div className="stats-row" style={{ marginBottom: 26 }}>
          <div className="stat">
            <div className="stat-value">{stats.total_policies}</div>
            <div className="stat-label">Policies on-chain</div>
          </div>
          <div className="stat">
            <div className="stat-value lime">{stats.active}</div>
            <div className="stat-label">Coverage live</div>
          </div>
          <div className="stat">
            <div className="stat-value amber">
              {stats.escrow_locked === 0n
                ? "0"
                : formatGen(stats.escrow_locked)}
            </div>
            <div className="stat-label">Held in escrow</div>
          </div>
          <div className="stat">
            <div className="stat-value">{stats.paid}</div>
            <div className="stat-label">Policies paid out</div>
          </div>
        </div>
      )}

      <div className="filter-pills" role="group" aria-label="Filter policies">
        <button
          className={filter === "active" ? "active" : ""}
          aria-pressed={filter === "active"}
          onClick={() => setFilter("active")}
        >
          Active
        </button>
        <button
          className={filter === "all" ? "active" : ""}
          aria-pressed={filter === "all"}
          onClick={() => setFilter("all")}
        >
          All
        </button>
      </div>

      {loading ? (
        <div className="page-loading" role="status">
          <span className="spinner" aria-hidden="true" /> Loading policies…
        </div>
      ) : (
        <>
          {visibleMy.length > 0 && (
            <section style={{ marginBottom: 34 }}>
              <h2 className="section-title">
                You're a party to{" "}
                <span className="accent">({visibleMy.length})</span>
              </h2>
              <div className="grid">
                {visibleMy.map((policy) => (
                  <PolicyCard
                    key={policy.id}
                    policy={policy}
                    me={wallet.address}
                    busy={busyId === policy.id}
                    now={now}
                    {...actions}
                  />
                ))}
              </div>
            </section>
          )}

          <h2 className="section-title">
            All policies{" "}
            <span className="accent">
              ({filter === "active" ? visibleOther.length : otherPolicies.length})
            </span>
          </h2>
          {otherPolicies.length === 0 ? (
            <div className="empty">
              <p>No policies yet.</p>
              <p>
                <a href="/create">Issue the first one →</a>
              </p>
            </div>
          ) : visibleOther.length === 0 ? (
            <div className="empty">
              <p>No open or active policies right now.</p>
              <p>
                <button className="ghost" onClick={() => setFilter("all")}>
                  Show all (including settled) →
                </button>
              </p>
            </div>
          ) : (
            <div className="grid">
              {visibleOther.map((policy) => (
                <PolicyCard
                  key={policy.id}
                  policy={policy}
                  me={wallet.address}
                  busy={busyId === policy.id}
                  now={now}
                  {...actions}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
