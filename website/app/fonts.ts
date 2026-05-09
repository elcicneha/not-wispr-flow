import localFont from "next/font/local";
import { Instrument_Sans, JetBrains_Mono } from "next/font/google";

export const recoleta = localFont({
  src: "../fonts/Recoleta Bold.woff2",
  variable: "--font-display-var",
  weight: "700",
  display: "swap",
  preload: true,
  fallback: ["Georgia", "Cambria", "Times New Roman", "serif"],
});

export const sans = Instrument_Sans({
  variable: "--font-sans-var",
  subsets: ["latin"],
  display: "swap",
  weight: ["400", "500", "600"],
  fallback: ["system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
});

export const mono = JetBrains_Mono({
  variable: "--font-mono-var",
  subsets: ["latin"],
  display: "swap",
  weight: ["400", "500"],
  fallback: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
});
