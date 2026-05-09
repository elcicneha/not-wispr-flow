export default function Asterisks() {
  return (
    <div
      aria-hidden="true"
      style={{
        textAlign: "center",
        padding: "48px 0 0",
        fontFamily: "var(--font-display-var), serif",
        fontSize: "clamp(24px, 3vw, 36px)",
        letterSpacing: "0.3em",
        color: "var(--ink)",
        opacity: 0.4,
        userSelect: "none",
      }}
    >
      * * * * * * * * *
    </div>
  );
}
