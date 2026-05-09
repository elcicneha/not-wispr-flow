import HandUnderline from "@/components/ui/HandUnderline";
import Button from "@/components/ui/Button";
import MenuBarClock from "@/components/ui/MenuBarClock";
import { REPO_URL } from "@/lib/content";
import Image from "next/image";

export default function Hero() {
  return (
    <section
      style={{
        minHeight: "92vh",
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: "0",
        padding: "80px 48px 80px 64px",
        position: "relative",
        alignItems: "center",
      }}
      className="hero-section"
    >
      {/* Left column — text */}
      <div style={{ maxWidth: "720px" }}>
        {/* Eyebrow tag */}
        <div
          style={{
            fontFamily: "var(--font-mono-var), monospace",
            fontSize: "12px",
            letterSpacing: "0.08em",
            color: "var(--ink-soft)",
            marginBottom: "32px",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            opacity: 0,
            animation: "fadeUp 0.5s ease forwards",
          }}
        >
          <span
            style={{
              padding: "3px 10px",
              border: "1.5px solid var(--ink-soft)",
              borderRadius: "999px",
            }}
          >
            macOS · Apple Silicon
          </span>
          <span>· FREE</span>
        </div>

        {/* h1 */}
        <h1>
          <span
            className="home-h1"
            style={{ overflow: "visible", animationDelay: "80ms" }}
          >
            Type with
          </span>
          <span
            className="home-h1"
            style={{
              position: "relative",
              overflow: "visible",
              animationDelay: "180ms",
            }}
          >
            your{" "}
            <span style={{ position: "relative", display: "inline-block" }}>
              voice.
              <HandUnderline delay={700} />
            </span>
          </span>
          <span className="home-h1" style={{ animationDelay: "280ms" }}>
            Free your
          </span>
          <span
            className="home-h1"
            style={{
              position: "relative",
              overflow: "visible",
              animationDelay: "380ms",
            }}
          >
            <span style={{ position: "relative", display: "inline-block" }}>
              fingers.
              <HandUnderline delay={900} />
            </span>
          </span>
        </h1>

        {/* Sub-line */}
        <p
          style={{
            fontSize: "var(--text-lead)",
            lineHeight: 1.5,
            color: "var(--ink-soft)",
            maxWidth: "520px",
            marginBottom: "40px",
            opacity: 0,
            animation: "fadeUp 0.6s ease 500ms forwards",
          }}
        >
          A free, offline voice-to-text menu bar app for macOS. Hold a key,
          speak, release — your words appear wherever your cursor is. Nothing
          leaves your Mac.
        </p>

        {/* CTA buttons */}
        <div
          style={{
            display: "flex",
            gap: "16px",
            flexWrap: "wrap",
            opacity: 0,
            animation: "fadeUp 0.6s ease 620ms forwards",
          }}
        >
          <Button href="#install" size="lg">
            Download for Mac ↓
          </Button>
          <Button
            href={REPO_URL}
            target="_blank"
            rel="noopener noreferrer"
            variant="outline"
            size="lg"
          >
            GitHub →
          </Button>
        </div>
      </div>

      {/* Right column — sticker cluster */}
      <div
        className="hero-cluster"
        style={{
          position: "relative",
          width: "100%",
          maxWidth: "480px",
          height: "580px",
          marginLeft: "auto",
          opacity: 0,
          animation: "fadeUp 0.7s ease 500ms forwards",
        }}
      >
        {/* macOS menu bar mockup — wide horizontal strip */}
        <div
          style={{
            position: "absolute",
            top: "20px",
            left: "0",
            right: "0",
            height: "38px",
            background: "var(--ink)",
            borderRadius: "8px",
            boxShadow: "5px 5px 0 var(--card), 5px 5px 0 2px var(--ink)",
            padding: "0 16px",
            display: "flex",
            alignItems: "center",
            justifyContent: "flex-end",
            gap: "18px",
            color: "var(--accent-contrast)",
            fontFamily: "var(--font-sans-var), sans-serif",
            fontSize: "12px",
            fontWeight: 500,
            zIndex: 4,
          }}
        >
          {/* App icon — highlighted (Not Wispr Flow) */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "3px",
              borderRadius: "5px",
              background: "var(--accent-contrast)",
              outline: "1.5px dashed var(--accent-contrast)",
              outlineOffset: "3px",
            }}
          >
            {/* Background here is --accent-contrast (lime in light theme, dark green in dark theme),
                so we want the opposite-colored icon for contrast. */}
            <Image
              src="/menu%20bar%20icon%20-%20dark.png"
              alt="Not Wispr Flow"
              width={16}
              height={16}
              className="block dark:hidden object-contain"
            />
            <Image
              src="/menu%20bar%20icon%20-%20light.png"
              alt="Not Wispr Flow"
              width={16}
              height={16}
              className="hidden dark:block object-contain"
            />
          </div>

          {/* Battery */}
          <svg width="26" height="12" viewBox="0 0 26 12" aria-hidden="true">
            <rect x="0.5" y="1" width="22" height="10" rx="2.5" stroke="currentColor" strokeWidth="1" fill="none" />
            <rect x="2.5" y="3" width="18" height="6" rx="1" fill="currentColor" />
            <rect x="23" y="4" width="2.5" height="4" rx="0.5" fill="currentColor" />
          </svg>

          {/* WiFi */}
          <svg width="18" height="13" viewBox="0 0 18 13" aria-hidden="true">
            <path d="M2 5 Q 9 -1, 16 5" stroke="currentColor" strokeWidth="1.4" fill="none" strokeLinecap="round" />
            <path d="M4.5 7.5 Q 9 4, 13.5 7.5" stroke="currentColor" strokeWidth="1.4" fill="none" strokeLinecap="round" />
            <circle cx="9" cy="10.5" r="1.4" fill="currentColor" />
          </svg>

          {/* Spotlight */}
          <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
            <circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.3" fill="none" />
            <line x1="9.5" y1="9.5" x2="12.5" y2="12.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
          </svg>

          {/* Control Center — two stacked toggle pills */}
          <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
            <rect x="1" y="2" width="12" height="3.4" rx="1.7" stroke="currentColor" strokeWidth="1.2" fill="none" />
            <circle cx="9.5" cy="3.7" r="1.1" fill="currentColor" />
            <rect x="1" y="8.6" width="12" height="3.4" rx="1.7" stroke="currentColor" strokeWidth="1.2" fill="none" />
            <circle cx="4.5" cy="10.3" r="1.1" fill="currentColor" />
          </svg>

          {/* Date / time — real-time, client-side */}
          <MenuBarClock />
        </div>

        {/* Annotation — anchored from the right to stay aligned with the
            app icon (which is the leftmost of the right-aligned icons in
            the menu bar; its distance from the right edge is constant). */}
        <div
          style={{
            position: "absolute",
            top: "62px",
            right: "178px",
            display: "flex",
            alignItems: "flex-start",
            gap: "4px",
            transform: "rotate(-2deg)",
            zIndex: 4,
          }}
        >
          <svg width="20" height="50" viewBox="0 0 20 50" aria-hidden="true" style={{ flexShrink: 0 }}>
            <path
              d="M10,46 C10,32 4,24 12,4"
              stroke="var(--ink-soft)"
              strokeWidth="1.6"
              fill="none"
              strokeLinecap="round"
            />
            <path
              d="M8,8 L12,2 L16,8"
              stroke="var(--ink-soft)"
              strokeWidth="1.6"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span
            style={{
              fontFamily: "var(--font-mono-var), monospace",
              fontSize: "11px",
              color: "var(--ink-soft)",
              letterSpacing: "0.04em",
              marginTop: "30px",
              maxWidth: "120px",
              lineHeight: 1.4,
            }}
          >
            lives in your menu bar
          </span>
        </div>

        {/* Receipt strip */}
        <div
          className="hero-receipt"
          style={{
            position: "absolute",
            top: "120px",
            left: "50%",
            transform: "translateX(-50%) rotate(-4deg)",
            width: "260px",
            background: "var(--card)",
            color: "var(--ink)",
            fontFamily: "var(--font-mono-var), monospace",
            fontSize: "13px",
            lineHeight: 1.7,
            letterSpacing: "0.02em",
            padding: "24px 24px 18px",
            boxShadow: "8px 8px 0 var(--ink)",
            zIndex: 2,
            /* zigzag bottom edge — like a torn-off receipt */
            clipPath:
              "polygon(0 0, 100% 0, 100% calc(100% - 12px), 95% 100%, 90% calc(100% - 12px), 85% 100%, 80% calc(100% - 12px), 75% 100%, 70% calc(100% - 12px), 65% 100%, 60% calc(100% - 12px), 55% 100%, 50% calc(100% - 12px), 45% 100%, 40% calc(100% - 12px), 35% 100%, 30% calc(100% - 12px), 25% 100%, 20% calc(100% - 12px), 15% 100%, 10% calc(100% - 12px), 5% 100%, 0 calc(100% - 12px))",
            paddingBottom: "30px",
          }}
        >
          {/* Header */}
          <div
            style={{
              fontFamily: "var(--font-display-var), serif",
              fontSize: "22px",
              fontWeight: 700,
              letterSpacing: "-0.02em",
              textAlign: "center",
              lineHeight: 1.05,
              marginBottom: "4px",
            }}
          >
            Not Wispr Flow
          </div>
          <div
            style={{
              fontSize: "10px",
              textAlign: "center",
              opacity: 0.7,
              letterSpacing: "0.1em",
              marginBottom: "12px",
            }}
          >
            voice-to-text · macOS
          </div>

          {/* Divider */}
          <div
            aria-hidden="true"
            style={{
              borderTop: "1.5px dashed var(--ink)",
              opacity: 0.5,
              margin: "8px 0 12px",
            }}
          />

          {/* Line items */}
          {[
            ["voice-to-text", "$0.00"],
            ["no cloud", "✓"],
            ["no account", "✓"],
            ["open source", "✓"],
            ["runs on your mac", "✓"],
            ["apple silicon", "✓"],
          ].map(([label, val]) => (
            <div
              key={label}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <span>{label}</span>
              <span style={{ fontWeight: 600 }}>{val}</span>
            </div>
          ))}

          {/* Divider */}
          <div
            aria-hidden="true"
            style={{
              borderTop: "1.5px dashed var(--ink)",
              opacity: 0.5,
              margin: "12px 0 8px",
            }}
          />

          {/* Total */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "baseline",
              fontFamily: "var(--font-display-var), serif",
              fontSize: "20px",
              fontWeight: 700,
              letterSpacing: "-0.01em",
            }}
          >
            <span>TOTAL</span>
            <span>$0.00</span>
          </div>

          {/* Divider */}
          <div
            aria-hidden="true"
            style={{
              borderTop: "1.5px dashed var(--ink)",
              opacity: 0.5,
              margin: "10px 0 10px",
            }}
          />

          {/* Footer */}
          <div
            style={{
              textAlign: "center",
              fontSize: "11px",
              opacity: 0.7,
              letterSpacing: "0.06em",
            }}
          >
            thank you ♡
          </div>
        </div>
      </div>

      <style>{`
        @media (max-width: 768px) {
          .hero-section {
            grid-template-columns: 1fr !important;
            padding: 48px 24px !important;
            min-height: auto !important;
          }
          .hero-cluster {
            margin: 64px auto 16px !important;
          }
        }
      `}</style>
    </section>
  );
}
