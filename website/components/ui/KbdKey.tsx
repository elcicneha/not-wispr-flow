interface KbdKeyProps {
  children: React.ReactNode;
  size?: "sm" | "md" | "lg";
}

export default function KbdKey({ children, size = "md" }: KbdKeyProps) {
  const padding =
    size === "lg" ? "10px 18px" : size === "md" ? "7px 13px" : "4px 9px";
  const fontSize =
    size === "lg" ? "18px" : size === "md" ? "14px" : "12px";

  return (
    <kbd
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        padding,
        fontFamily: "var(--font-mono-var), monospace",
        fontSize,
        fontWeight: 500,
        fontStyle: "normal",
        color: "var(--ink)",
        background: "var(--card)",
        border: "2px solid var(--border)",
        borderRadius: "6px",
        boxShadow: "0 4px 0 0 var(--border)",
        transform: "translateY(-1px)",
        letterSpacing: "0.02em",
        userSelect: "none",
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </kbd>
  );
}
