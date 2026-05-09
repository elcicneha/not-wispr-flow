import type {
  AnchorHTMLAttributes,
  ButtonHTMLAttributes,
  ReactNode,
} from "react";
import { twMerge } from "tailwind-merge";

type Variant = "primary" | "outline" | "chip";
type Size = "sm" | "md" | "lg";

type CommonProps = {
  children: ReactNode;
  variant?: Variant;
  size?: Size;
  className?: string;
};

type AnchorProps = CommonProps &
  Omit<AnchorHTMLAttributes<HTMLAnchorElement>, keyof CommonProps> & {
    href: string;
  };

type NativeButtonProps = CommonProps &
  Omit<ButtonHTMLAttributes<HTMLButtonElement>, keyof CommonProps> & {
    href?: undefined;
  };

type ButtonProps = AnchorProps | NativeButtonProps;

const base =
  "inline-flex items-center gap-2 border-border no-underline cursor-pointer transition-all duration-150";

// Sizes carry only dimensions (padding, font-size, border-width, radius).
const sizes: Record<Size, string> = {
  sm: "py-1.5 px-3.5 text-xs border-[1.5px] rounded-md",
  md: "py-3.5 px-7 text-[clamp(16px,1.4vw,20px)] border-2 rounded",
  lg: "py-4 px-8 text-[clamp(18px,1.6vw,24px)] border-2 rounded",
};

// Variants carry treatment identity (bg, text color, typography, shadows).
const variants: Record<Variant, string> = {
  primary:
    "bg-accent text-accent-contrast font-display font-bold tracking-[-0.01em] shadow-ink-soft shadow-[4px_4px_0_var(--tw-shadow-color)] hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-ink-soft/90 hover:shadow-[6px_8px_0_var(--tw-shadow-color)] active:translate-x-px active:translate-y-px active:shadow-ink-soft active:shadow-[2px_2px_0_var(--tw-shadow-color)]",
  outline:
    "bg-transparent text-ink font-display font-bold tracking-[-0.01em] hover:bg-bg-soft",
  chip: "bg-transparent text-ink-soft font-mono tracking-[0.04em] hover:bg-bg-soft shrink-0",
};

export default function Button(props: ButtonProps) {
  const { children, variant = "primary", size = "md", className, ...rest } = props;
  const classes = twMerge(base, sizes[size], variants[variant], className);

  if ("href" in props && props.href !== undefined) {
    return (
      <a className={classes} {...(rest as AnchorHTMLAttributes<HTMLAnchorElement>)}>
        {children}
      </a>
    );
  }

  return (
    <button className={classes} {...(rest as ButtonHTMLAttributes<HTMLButtonElement>)}>
      {children}
    </button>
  );
}
