import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";

interface InlineCodeProps extends HTMLAttributes<HTMLElement> {
  children: ReactNode;
}

export default function InlineCode({ children, className, ...rest }: InlineCodeProps) {
  return (
    <code
      className={cn(
        "text-[0.9em] bg-white/20 border border-border rounded px-1.5 py-0.5 mx-0.5",
        className
      )}
      {...rest}
    >
      {children}
    </code>
  );
}
