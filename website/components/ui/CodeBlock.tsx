"use client";

import { useState } from "react";
import Button from "./Button";

interface CodeBlockProps {
  code: string;
}

export default function CodeBlock({ code }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { }
  }

  return (
    <div className="flex items-center justify-between gap-4 bg-card border-border border-2 px-5 py-4 rounded-lg mt-4 shadow-[3px_3px_0_var(--border)]">
      <code>
        {code}
      </code>
      <Button
        onClick={copy}
        aria-label="Copy to clipboard"
        variant="chip"
        size="sm"
      >
        {copied ? "copied!" : "copy"}
      </Button>
    </div>
  );
}
