interface StarburstProps {
  size?: number;
  topText: string;
  bottomText: string;
  rotation?: number;
}

export default function Starburst({
  size = 160,
  topText,
  bottomText,
  rotation = 0,
}: StarburstProps) {
  const points = 14;
  const outerR = 95;
  const innerR = 68;
  const cx = 100;
  const cy = 100;

  let d = "";
  for (let i = 0; i < points * 2; i++) {
    const angle = (Math.PI * i) / points - Math.PI / 2;
    const r = i % 2 === 0 ? outerR : innerR;
    const x = cx + Math.cos(angle) * r;
    const y = cy + Math.sin(angle) * r;
    d += i === 0
      ? `M${x.toFixed(2)},${y.toFixed(2)}`
      : ` L${x.toFixed(2)},${y.toFixed(2)}`;
  }
  d += " Z";

  return (
    <svg
      viewBox="0 0 200 200"
      width={size}
      height={size}
      style={{
        transform: `rotate(${rotation}deg)`,
        display: "block",
        filter: "drop-shadow(4px 4px 0 var(--ink))",
      }}
      aria-hidden="true"
    >
      <path
        d={d}
        fill="var(--card)"
        stroke="var(--ink)"
        strokeWidth="3"
        strokeLinejoin="round"
      />
      {/* Inner ring for vintage seal feel */}
      <circle
        cx={cx}
        cy={cy}
        r="58"
        fill="none"
        stroke="var(--ink)"
        strokeWidth="1.5"
        strokeDasharray="2 4"
        opacity="0.6"
      />
      <text
        x={cx}
        y="92"
        textAnchor="middle"
        fontFamily="var(--font-display-var), serif"
        fontSize="44"
        fontWeight="700"
        fill="var(--ink)"
        style={{ letterSpacing: "-0.02em" }}
      >
        {topText}
      </text>
      <text
        x={cx}
        y="124"
        textAnchor="middle"
        fontFamily="var(--font-mono-var), monospace"
        fontSize="13"
        fontWeight="600"
        fill="var(--ink)"
        style={{ letterSpacing: "0.18em" }}
      >
        {bottomText}
      </text>
    </svg>
  );
}
