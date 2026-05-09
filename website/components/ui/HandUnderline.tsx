interface HandUnderlineProps {
  delay?: number;
}

export default function HandUnderline({ delay = 0 }: HandUnderlineProps) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 240 16"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      style={{
        position: "absolute",
        bottom: "-8px",
        left: "-4px",
        width: "calc(100% + 8px)",
        height: "16px",
        overflow: "visible",
        pointerEvents: "none",
      }}
    >
      <path
        d="M4 10 Q 40 4, 80 8 T 160 6 T 236 9"
        stroke="var(--ink)"
        strokeWidth="5"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
        style={{
          strokeDasharray: 300,
          strokeDashoffset: 300,
          animation: `underlineDraw 0.6s cubic-bezier(0.22, 1, 0.36, 1) ${delay}ms forwards`,
        }}
      />
    </svg>
  );
}
