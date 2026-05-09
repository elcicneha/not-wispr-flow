interface MarqueeProps {
  items: string[];
  separator?: string;
}

export default function Marquee({ items, separator = "★" }: MarqueeProps) {
  // Render the sequence twice for a seamless loop. Each pair (item + separator)
  // contributes consistent spacing — `marginLeft` between item and separator,
  // and `paddingRight` between separator and the next pair. Same value (48px)
  // on both, so the visual rhythm is steady across the loop seam too.
  const sequence = [...items, ...items];

  return (
    <div
      aria-hidden="true"
      className="marquee-wrapper"
      style={{
        overflow: "hidden",
        borderTop: "3px solid var(--border)",
        borderBottom: "3px solid var(--border)",
        padding: "18px 0",
        background: "var(--card)",
        cursor: "default",
      }}
    >
      <div
        className="marquee-track"
        style={{
          display: "flex",
          alignItems: "center",
          width: "max-content",
          animation: "marqueeScroll 60s linear infinite",
        }}
      >
        {sequence.map((item, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              alignItems: "center",
              flexShrink: 0,
              paddingRight: "48px",
            }}
          >
            <span
              style={{
                fontFamily: "var(--font-display-var), serif",
                fontSize: "clamp(22px, 2.2vw, 32px)",
                fontWeight: 700,
                color: "var(--ink)",
                letterSpacing: "-0.01em",
                whiteSpace: "nowrap",
              }}
            >
              {item}
            </span>
            <span
              aria-hidden="true"
              style={{
                marginLeft: "48px",
                fontFamily: "var(--font-display-var), serif",
                fontSize: "clamp(20px, 2vw, 28px)",
                color: "var(--ink)",
                opacity: 0.5,
                lineHeight: 1,
              }}
            >
              {separator}
            </span>
          </div>
        ))}
      </div>
      <style>{`
        .marquee-wrapper:hover .marquee-track {
          animation-play-state: paused;
        }
      `}</style>
    </div>
  );
}
