import TextLink from "@/components/ui/TextLink";
import { REPO_URL } from "@/lib/content";

export default function Footer() {
  return (
    <footer
      style={{
        padding: "80px 64px 56px",
        borderTop: "1.5px solid var(--border)",
      }}
      className="footer-section"
    >
      {/* Wordmark */}
      <div className="font-display text-text-h2 text-ink leading-[0.95] tracking-[-0.03em] mb-4">
        Not Wispr Flow
      </div>
      <p className="font-medium text-[clamp(18px,_2vw,_26px)] tracking-[-0.01em] mb-12 text-ink-soft" >
        Built so you can stop typing.
      </p>

      {/* Credits */}
      <p
        style={{
          fontFamily: "var(--font-mono-var), monospace",
          fontSize: "13px",
          color: "var(--ink-soft)",
          letterSpacing: "0.03em",
          lineHeight: 1.8,
        }}
      >
        Inspired by{" "}
        <TextLink href="https://wisprflow.ai" target="_blank" rel="noopener noreferrer">
          Wispr Flow
        </TextLink>
        {" · "}
        Whisper via{" "}
        <TextLink
          href="https://github.com/ml-explore/mlx-examples/tree/main/whisper"
          target="_blank"
          rel="noopener noreferrer"
        >
          mlx-whisper
        </TextLink>
        {" · "}
        Open source on{" "}
        <TextLink href={REPO_URL} target="_blank" rel="noopener noreferrer">
          GitHub
        </TextLink>
      </p>

      <style>{`
        @media (max-width: 768px) {
          .footer-section { padding: 64px 24px 48px !important; }
        }
      `}</style>
    </footer>
  );
}
