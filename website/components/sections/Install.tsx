import CodeBlock from "@/components/ui/CodeBlock";
import Button from "@/components/ui/Button";
import InlineCode from "@/components/ui/InlineCode";
import { installSteps, DOWNLOAD_ZIP_URL } from "@/lib/content";

export default function Install() {
  return (
    <section
      id="install"
      style={{
        padding: "100px 64px",
        borderTop: "1.5px solid var(--border)",
        scrollMarginTop: "80px",
      }}
      className="install-section"
    >
      <div className="mb-20">
        <h2>
          Installation steps
        </h2>
        <p className="font-mono" >
          Three steps. Five minutes. One password prompt.
        </p>
      </div>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "0",
        }}
      >
        {/* Step 01 */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "200px 1fr",
            gap: "32px",
            paddingBottom: "72px",
            borderBottom: "1px solid var(--border)",
            marginBottom: "72px",
            alignItems: "flex-start",
          }}
          className="install-step"
        >
          <div
            style={{
              fontFamily: "var(--font-display-var), serif",
              fontSize: "clamp(80px, 10vw, 140px)",
              fontWeight: 700,
              lineHeight: 0.85,
              letterSpacing: "-0.04em",
              color: "var(--ink)",
              opacity: 0.15,
              userSelect: "none",
            }}
          >
            01
          </div>
          <div style={{ paddingTop: "8px" }}>
            <h3>
              Download.
            </h3>
            <p
              style={{
                fontSize: "var(--text-lead)",
                color: "var(--ink-soft)",
                lineHeight: 1.5,
                marginBottom: "24px",
              }}
            >
              Hit the button. You'll get a ZIP from the GitHub repo.
            </p>
            <Button href={DOWNLOAD_ZIP_URL} size="md">
              Download ZIP →
            </Button>
          </div>
        </div>

        {/* Step 02 */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "200px 1fr",
            gap: "32px",
            paddingBottom: "72px",
            borderBottom: "1px solid var(--border)",
            marginBottom: "72px",
            alignItems: "flex-start",
          }}
          className="install-step"
        >
          <div
            style={{
              fontFamily: "var(--font-display-var), serif",
              fontSize: "clamp(80px, 10vw, 140px)",
              fontWeight: 700,
              lineHeight: 0.85,
              letterSpacing: "-0.04em",
              color: "var(--ink)",
              opacity: 0.15,
              userSelect: "none",
            }}
          >
            02
          </div>
          <div style={{ paddingTop: "8px" }}>
            <h3>
              Run the installer.
            </h3>
            <p
              style={{
                fontSize: "var(--text-lead)",
                color: "var(--ink-soft)",
                lineHeight: 1.5,
                marginBottom: "8px",
              }}
            >
              Right-click the unzipped{" "}
              <InlineCode>not-wispr-flow</InlineCode>{" "}
              folder → <strong>New Terminal at Folder</strong>, then paste:
            </p>
            <CodeBlock code="./install.sh" />
            <p
              style={{
                marginTop: "16px",
                fontSize: "14px",
                color: "var(--ink-soft)",
                fontFamily: "var(--font-mono-var), monospace",
                letterSpacing: "0.02em",
              }}
            >
              Asks for your Mac password once. Takes 5–10 min on first run.
            </p>

            {/* Placeholder for screen recording
            <div
              style={{
                marginTop: "32px",
                border: "2px dashed var(--border)",
                borderRadius: "12px",
                padding: "32px",
                textAlign: "center",
                opacity: 0.5,
              }}
            >
              <p
                style={{
                  fontFamily: "var(--font-mono-var), monospace",
                  fontSize: "13px",
                  color: "var(--ink-soft)",
                  letterSpacing: "0.04em",
                }}
              >
                [ screen recording coming soon ]
              </p>
            </div> */}
          </div>
        </div>

        {/* Step 03 */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "200px 1fr",
            gap: "32px",
            alignItems: "flex-start",
          }}
          className="install-step"
        >
          <div
            style={{
              fontFamily: "var(--font-display-var), serif",
              fontSize: "clamp(80px, 10vw, 140px)",
              fontWeight: 700,
              lineHeight: 0.85,
              letterSpacing: "-0.04em",
              color: "var(--ink)",
              opacity: 0.15,
              userSelect: "none",
            }}
          >
            03
          </div>
          <div style={{ paddingTop: "8px" }}>
            <h3>
              Grant permissions.
            </h3>
            <p
              style={{
                fontSize: "var(--text-lead)",
                color: "var(--ink-soft)",
                lineHeight: 1.5,
                marginBottom: "24px",
              }}
            >
              Open <strong>Not Wispr Flow</strong> from Spotlight. In System
              Settings → Privacy & Security, give it access to:
            </p>
            <div
              style={{
                display: "flex",
                gap: "12px",
                flexWrap: "wrap",
                marginBottom: "20px",
              }}
            >
              {["Microphone", "Accessibility", "Input Monitoring"].map((p) => (
                <span
                  key={p}
                  style={{
                    padding: "8px 18px",
                    background: "var(--card)",
                    border: "2px solid var(--border)",
                    borderRadius: "999px",
                    fontFamily: "var(--font-mono-var), monospace",
                    fontSize: "13px",
                    fontWeight: 500,
                    letterSpacing: "0.04em",
                    color: "var(--ink)",
                    boxShadow: "2px 2px 0 var(--border)",
                  }}
                >
                  {p}
                </span>
              ))}
            </div>
            <p
              style={{
                fontSize: "14px",
                color: "var(--ink-soft)",
                fontFamily: "var(--font-mono-var), monospace",
                letterSpacing: "0.02em",
              }}
            >
              You only need to do this once.
            </p>
          </div>
        </div>
      </div>

      <style>{`
        @media (max-width: 768px) {
          .install-section { padding: 64px 24px !important; }
          .install-step { grid-template-columns: 1fr !important; }
          .install-step > div:first-child { font-size: 64px !important; opacity: 0.1 !important; }
        }
      `}</style>
    </section>
  );
}
