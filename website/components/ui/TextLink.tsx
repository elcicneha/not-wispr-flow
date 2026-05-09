import type { AnchorHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";

interface TextLinkProps extends AnchorHTMLAttributes<HTMLAnchorElement> {
  children: ReactNode;
}

export default function TextLink({ children, className, ...rest }: TextLinkProps) {
  return (
    <a className={cn("underline underline-offset-[3px]", className)} {...rest}>
      {children}
    </a>
  );
}
