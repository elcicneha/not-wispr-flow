"use client";

import { useEffect, useState } from "react";
import Button from "./Button";

export default function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    setTheme(document.documentElement.classList.contains("dark") ? "dark" : "light");
  }, []);

  function toggle() {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    document.documentElement.classList.toggle("dark", next === "dark");
    try {
      localStorage.setItem("theme", next);
    } catch { }
  }

  return (
    <Button
      variant="chip"
      size="sm"
      onClick={toggle}
      aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
      aria-pressed={theme === "dark"}
      className="rounded-full select-none"
    >
      <span className="text-sm">{theme === "light" ? "◐" : "◑"}</span>
      <span>{theme === "light" ? "dark" : "light"}</span>
    </Button>
  );
}
