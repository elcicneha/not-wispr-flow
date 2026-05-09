import type { AnchorHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";

interface TextLinkProps extends AnchorHTMLAttributes<HTMLAnchorElement> {
  children: ReactNode;
}

export default function TextLink({ children, className, ...rest }: TextLinkProps) {
  return (
    <a className={cn("underline underline-offset-[3px] font-mono text-xs tracking-[0.04em] text-ink-soft", className)} {...rest}>
      {children}
    </a>
  );
}
