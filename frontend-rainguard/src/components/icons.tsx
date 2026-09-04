/**
 * Custom-drawn icons for RainGuard — no stock emoji, so the UI keeps its own
 * visual language. All icons inherit `currentColor`; wrap with `.ic` for
 * sizing.
 */

interface IconProps {
  size?: number;
}

function base(size: number) {
  return {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };
}

/** A falling raindrop — rainfall triggers. */
export function DropletIcon({ size = 20 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M12 3.2c3.1 3.4 5.1 6.1 5.1 8.5a5.1 5.1 0 1 1-10.2 0C6.9 9.3 8.9 6.6 12 3.2Z" />
      <path d="M9.4 14.6a2.7 2.7 0 0 0 2.6 2.7" />
    </svg>
  );
}

/** A thermometer — temperature triggers. */
export function ThermometerIcon({ size = 20 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M14.5 5.5a2.5 2.5 0 0 0-5 0v8.6a4 4 0 1 0 5 0V5.5Z" />
      <path d="M12 10.5V5.5" />
      <circle cx="12" cy="15.6" r="1.1" fill="currentColor" stroke="none" />
    </svg>
  );
}

/** A lightning bolt — auto settlement / money moving itself. */
export function BoltIcon({ size = 20 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M13.2 2.8 4.5 13.2h5.2l-1 8 8.8-10.4h-5.2l.9-8Z" />
    </svg>
  );
}

/** A shield — coverage / escrow protection. */
export function ShieldIcon({ size = 20 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M12 3 19 6v5.5c0 4.6-2.9 8-7 9.5-4.1-1.5-7-4.9-7-9.5V6l7-3Z" />
      <path d="m9.2 12 2 2 3.6-3.8" />
    </svg>
  );
}

/** A radar dish — the live board / monitoring. */
export function RadarIcon({ size = 20 }: IconProps) {
  return (
    <svg {...base(size)}>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5.4" />
      <circle cx="12" cy="12" r="1.8" />
      <path d="M12 12 18 6" />
    </svg>
  );
}