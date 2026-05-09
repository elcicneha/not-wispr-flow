import Image from "next/image";
import ThemeToggle from "@/components/ui/ThemeToggle";
import TextLink from "@/components/ui/TextLink";
import { REPO_URL } from "@/lib/content";

export default function Header() {
  return (
    <header className="sticky top-0 z-[100] flex items-center justify-between px-8 py-[0.875rem] border-b-[1.5px] border-border bg-bg backdrop-blur-[8px]">
      {/* Wordmark */}
      <a
        href="/"
        className="font-display text-xl font-bold text-ink no-underline tracking-[-0.02em] flex items-center gap-1.5"
      >
        <Image
          src="/logo-light-mode.png"
          alt=""
          width={32}
          height={32}
          className="block dark:hidden"
          priority
        />
        <Image
          src="/logo-dark-mode.png"
          alt=""
          width={32}
          height={32}
          className="hidden dark:block"
          priority
        />
        Not Wispr Flow
      </a>

      {/* Right controls */}
      <div className="flex items-center gap-6" >
        <TextLink
          href="#install">
          Download
        </TextLink>
        <TextLink
          href={REPO_URL}
          target="_blank"
          rel="noopener noreferrer"
        >
          GitHub
        </TextLink>
        <ThemeToggle />
      </div>
    </header>
  );
}
