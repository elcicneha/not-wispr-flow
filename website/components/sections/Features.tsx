import { features } from "@/lib/content";

export default function Features() {
  return (
    <section
      style={{
        padding: "120px 64px",
        borderTop: "1.5px solid var(--border)",
      }}
      className="features-section"
    >
      <h2
        style={{
          fontFamily: "var(--font-display-var), serif",
          fontSize: "var(--text-h2)",
          fontWeight: 700,
          lineHeight: 0.95,
          letterSpacing: "-0.03em",
          color: "var(--ink)",
          marginBottom: "80px",
        }}
      >
        What it does.
      </h2>

      <div className="features-list">
        {features.map((f, i) => (
          <article
            key={f.title}
            className="feature-row"
            style={{
              display: "grid",
              gridTemplateColumns: "minmax(220px, 1.1fr) 1.4fr",
              gap: "64px",
              padding: "36px 0",
              borderBottom:
                i < features.length - 1
                  ? "1.5px dashed var(--border)"
                  : "none",
              alignItems: "baseline",
            }}
          >
            <h3
              style={{
                fontFamily: "var(--font-display-var), serif",
                fontSize: "clamp(28px, 3.2vw, 42px)",
                fontWeight: 700,
                lineHeight: 1.05,
                letterSpacing: "-0.02em",
                color: "var(--ink)",
                margin: 0,
              }}
            >
              {f.title}
            </h3>
            <p
              style={{
                fontSize: "18px",
                color: "var(--ink-soft)",
                lineHeight: 1.6,
                maxWidth: "560px",
              }}
            >
              {f.body}
            </p>
          </article>
        ))}
      </div>

      <style>{`
        @media (max-width: 768px) {
          .features-section {
            padding: 72px 24px !important;
          }
          .feature-row {
            grid-template-columns: 1fr !important;
            gap: 12px !important;
            padding: 28px 0 !important;
          }
        }
      `}</style>
    </section>
  );
}
