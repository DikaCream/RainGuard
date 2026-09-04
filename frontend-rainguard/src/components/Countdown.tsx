import { useEffect, useState } from "react";

function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s % 60}s`;
  return `${s}s`;
}

function formatClock(unixSeconds: number): string {
  return new Date(unixSeconds * 1000).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface CountdownProps {
  target: number; // unix seconds
  /** When the target is in the future: "{prefix} {x}". */
  prefix?: string;
  /** When the target has passed: shown verbatim. */
  passed?: string;
}

/** Live countdown to a unix timestamp, ticking once per second. */
export default function Countdown({ target, prefix = "In", passed = "Now" }: CountdownProps) {
  const [now, setNow] = useState(() => Math.floor(Date.now() / 1000));

  useEffect(() => {
    const id = setInterval(() => setNow(Math.floor(Date.now() / 1000)), 1000);
    return () => clearInterval(id);
  }, []);

  if (now >= target) {
    return <span className="countdown passed">{passed}</span>;
  }
  return (
    <span className="countdown">
      {prefix} <strong>{formatDuration(target - now)}</strong>
      <span className="muted" style={{ fontSize: "0.75rem" }}>
        {" "}
        (until {formatClock(target)})
      </span>
    </span>
  );
}
