interface LogoProps {
  size?: number;
  withWordmark?: boolean;
}

/**
 * Brand mark: a droplet over a measuring line — the trigger (weather) and the
 * payout scale. Sky-blue drop, amber tick where the threshold sits.
 */
export default function Logo({ size = 30, withWordmark = true }: LogoProps) {
  return (
    <span className="logo">
      <svg
        width={size}
        height={size}
        viewBox="0 0 32 32"
        fill="none"
        aria-hidden="true"
        style={{ flexShrink: 0 }}
      >
        <rect
          x="2"
          y="2"
          width="28"
          height="28"
          rx="9"
          fill="#0c1626"
          stroke="rgba(255,255,255,0.22)"
        />
        {/* droplet (rain / the trigger) */}
        <path
          d="M16 7c3.4 3.6 5.6 6.6 5.6 9.2a5.6 5.6 0 1 1-11.2 0C10.4 13.6 12.6 10.6 16 7Z"
          fill="#4fc3f7"
        />
        {/* measurement line + threshold tick (the payout scale) */}
        <path
          d="M6 25.5h20"
          stroke="rgba(255,255,255,0.5)"
          strokeWidth="1.6"
          strokeLinecap="round"
        />
        <path
          d="M16 25.5V21"
          stroke="#ffb74d"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </svg>
      {withWordmark && (
        <span className="logo-word">
          Rain<span>Guard</span>
        </span>
      )}
    </span>
  );
}
