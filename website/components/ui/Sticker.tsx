interface StickerProps {
  children: React.ReactNode;
  rotation?: number;
  tone?: "lime" | "neutral" | "dark";
  size?: "sm" | "md";
}

export default function Sticker({
  children,
  rotation = 0,
  tone = "neutral",
  size = "md",
}: StickerProps) {
  const bg =
    tone === "lime"
      ? "var(--bg)"
      : tone === "dark"
      ? "var(--ink)"
      : "var(--card)";
  const color = tone === "dark" ? "var(--accent-contrast)" : "var(--ink)";
  const border = "var(--border)";

  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        padding: size === "sm" ? "6px 12px" : "10px 20px",
        background: bg,
        color,
        border: `2px solid ${border}`,
        borderRadius: "999px",
        transform: `rotate(${rotation}deg)`,
        fontFamily: "var(--font-mono-var), monospace",
        fontSize: size === "sm" ? "11px" : "13px",
        fontWeight: 500,
        letterSpacing: "0.06em",
        whiteSpace: "nowrap",
        boxShadow: `3px 3px 0 ${border}`,
        userSelect: "none",
      }}
    >
      {children}
    </div>
  );
}
