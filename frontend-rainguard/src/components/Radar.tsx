import type { Policy, Stats } from "../lib/types";
import { formatGen } from "../lib/client";

interface RadarProps {
  policies: Policy[];
  stats: Stats | null;
}

interface Blip {
  left: number;
  top: number;
  id: number;
  metric: "rainfall" | "temperature";
}

/** Map lat/lon to a position inside the radar circle. */
function toBlips(policies: Policy[]): Blip[] {
  const pts = policies
    .map((p) => ({ lat: Number(p.lat), lon: Number(p.lon), id: p.id, metric: p.metric }))
    .filter((p) => Number.isFinite(p.lat) && Number.isFinite(p.lon));

  if (pts.length === 0) return [];

  const cLat = pts.reduce((s, p) => s + p.lat, 0) / pts.length;
  const cLon = pts.reduce((s, p) => s + p.lon, 0) / pts.length;
  const rangeLat = Math.max(...pts.map((p) => p.lat)) - Math.min(...pts.map((p) => p.lat));
  const rangeLon = Math.max(...pts.map((p) => p.lon)) - Math.min(...pts.map((p) => p.lon));
  // Spread factor: keep a visible spread even for nearly-identical coords.
  const spread = Math.max(rangeLat, rangeLon, 10);

  return pts.map((p, i) => {
    // Nudge overlapping contacts apart a touch so every policy stays visible.
    const nudge = pts.length > 1 ? 5.5 : 0;
    const angle = (i / pts.length) * Math.PI * 2 + Math.PI / 4;
    let left = 50 + ((p.lon - cLon) / spread) * 33 + Math.cos(angle) * nudge;
    let top = 50 - ((p.lat - cLat) / spread) * 33 + Math.sin(angle) * nudge;
    left = Math.min(86, Math.max(14, left));
    top = Math.min(86, Math.max(14, top));
    return { left, top, id: p.id, metric: p.metric };
  });
}

/**
 * A live radar of the coverage market: every on-chain policy is a contact
 * plotted by its real coordinates, swept by a rotating beam.
 */
export default function Radar({ policies, stats }: RadarProps) {
  const blips = toBlips(policies);

  return (
    <div className="radar-box">
      <div className="radar-scene">
        <div className="radar-3d">
          <div className="radar" role="img" aria-label="Radar of live coverage policies">
            <div className="radar-ring r1" />
            <div className="radar-ring r2" />
            <div className="radar-ring r3" />
            <div className="radar-dash" />
            <div className="radar-cross cx" />
            <div className="radar-cross cy" />
            <div className="radar-sweep" />
            <span className="radar-tick tn">N</span>
            <span className="radar-tick ts">S</span>
            <span className="radar-tick te">E</span>
            <span className="radar-tick tw">W</span>
            {blips.map((b) => (
              <span
                key={b.id}
                className={`radar-blip ${b.metric}`}
                style={{ left: `${b.left}%`, top: `${b.top}%` }}
                title={`Policy #${b.id}: ${b.metric}`}
              >
                <span className="radar-ping" />
                <span className="radar-blip-dot" />
                <span className="radar-blip-tag">#{b.id}</span>
              </span>
            ))}
            <span className="radar-center" />
          </div>
        </div>
        <div className="radar-floor" aria-hidden="true" />
      </div>

      <div className="radar-readout mono">
        <div>
          <span className="rr-label">SYS</span> radar online /{" "}
          {blips.length} contact{blips.length === 1 ? "" : "s"}
        </div>
        <div>
          <span className="rr-label">ESCROW</span>{" "}
          {stats ? formatGen(stats.escrow_locked) : "–"}
        </div>
        <div>
          <span className="rr-label">OPEN</span> {stats?.open ?? "–"} /{" "}
          <span className="rr-label">LIVE</span> {stats?.active ?? "–"} /{" "}
          <span className="rr-label">PAID</span> {stats?.paid ?? "–"}
        </div>
      </div>
    </div>
  );
}