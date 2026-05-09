import KbdKey from "@/components/ui/KbdKey";
import InlineCode from "../ui/InlineCode";

export default function DemoSection() {
  return (
    <section
      style={{
        padding: "100px 64px",
        borderTop: "1.5px solid var(--border)",
      }}
      className="demo-section"
    >
      {/* Section header */}
      <h2
        style={{
          fontFamily: "var(--font-display-var), serif",
          fontSize: "var(--text-h2)",
          fontWeight: 700,
          lineHeight: 0.95,
          letterSpacing: "-0.03em",
          color: "var(--ink)",
          marginBottom: "64px",
        }}
      >
        See it in action.
      </h2>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "3fr 2fr",
          gap: "48px",
          alignItems: "flex-start",
        }}
        className="demo-grid"
      >
        {/* Video */}
        <div>
          <div
            style={{
              border: "3px solid var(--border)",
              borderRadius: "16px",
              overflow: "hidden",
              boxShadow: "8px 8px 0 var(--border)",
              background: "var(--card)",
            }}
          >
            <video
              src="/demo.mp4"
              poster="/demo-poster.png"
              autoPlay
              muted
              loop
              playsInline
              preload="metadata"
              aria-label="Demo of Not Wispr Flow transcribing speech in real time"
              style={{
                width: "100%",
                height: "auto",
                display: "block",
              }}
            />
          </div>
          <p
            style={{
              marginTop: "16px",
              fontFamily: "var(--font-mono-var), monospace",
              fontSize: "13px",
              color: "var(--ink-soft)",
              letterSpacing: "0.02em",
            }}
          >
            Hold Control, speak, release. Your transcript types itself.
          </p>
        </div>

        {/* Usage cards */}
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          {/* Hold mode */}
          <div
            style={{
              background: "var(--card)",
              border: "2px solid var(--border)",
              borderRadius: "16px",
              padding: "28px",
            }}
          >
            <div
              style={{
                fontFamily: "var(--font-mono-var), monospace",
                fontSize: "11px",
                letterSpacing: "0.1em",
                color: "var(--ink-soft)",
                marginBottom: "16px",
              }}
            >
              HOLD MODE
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                flexWrap: "wrap",
                marginBottom: "12px",
              }}
            >
              <KbdKey size="lg">Ctrl</KbdKey>
              <span
                style={{
                  fontFamily: "var(--font-mono-var), monospace",
                  fontSize: "13px",
                  color: "var(--ink-soft)",
                }}
              >
                hold → speak → release
              </span>
            </div>
            <p
              style={{
                fontSize: "15px",
                color: "var(--ink-soft)",
                lineHeight: 1.4,
              }}
            >
              Hold to record, release to transcribe. Quick and fluid.
            </p>
          </div>

          {/* Toggle mode */}
          <div
            style={{
              background: "var(--card)",
              border: "2px solid var(--border)",
              borderRadius: "16px",
              padding: "28px",
            }}
          >
            <div
              style={{
                fontFamily: "var(--font-mono-var), monospace",
                fontSize: "11px",
                letterSpacing: "0.1em",
                color: "var(--ink-soft)",
                marginBottom: "16px",
              }}
            >
              TOGGLE MODE
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                flexWrap: "wrap",
                marginBottom: "12px",
              }}
            >
              <KbdKey size="lg">Ctrl</KbdKey>
              <span
                style={{
                  fontFamily: "var(--font-mono-var), monospace",
                  fontSize: "13px",
                  color: "var(--ink-soft)",
                }}
              >
                +
              </span>
              <KbdKey size="lg">Space</KbdKey>
              <span
                style={{
                  fontFamily: "var(--font-mono-var), monospace",
                  fontSize: "13px",
                  color: "var(--ink-soft)",
                }}
              >
                → speak → Ctrl
              </span>
            </div>
            <p
              style={{
                fontSize: "15px",
                color: "var(--ink-soft)",
                lineHeight: 1.4,
              }}
            >
              Hands-free. Start, then stop when done. Good for longer dictation.
            </p>
          </div>

          {/* Bonus note */}
          <div
            style={{
              background: "transparent",
              border: "1.5px dashed var(--border)",
              borderRadius: "12px",
              padding: "20px 24px",
              display: "flex",
              gap: "12px",
              alignItems: "flex-start",
            }}
          >
            <span
              style={{
                fontFamily: "var(--font-display-var), serif",
                fontSize: "22px",
                lineHeight: 1,
                color: "var(--ink)",
                flexShrink: 0,
              }}
            >
              ♫
            </span>
            <p
              style={{
                fontSize: "14px",
                color: "var(--ink-soft)",
                lineHeight: 1.5,
              }}
            >
              Listening to music? The app automatically pauses playback when you
              start recording and resumes after. <br />
              <span className="mt-2 inline-block">You can change this in{" "}
                <InlineCode>config.py</InlineCode></span>
            </p>
          </div>
        </div>
      </div>

      <style>{`
        @media (max-width: 768px) {
          .demo-section { padding: 64px 24px !important; }
          .demo-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </section>
  );
}
