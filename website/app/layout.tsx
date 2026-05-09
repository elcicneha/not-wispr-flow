import type { Metadata } from "next";
import { recoleta, sans, mono } from "./fonts";
import { themeScript } from "./theme-script";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://elcicneha.github.io/not-wispr-flow"),
  title: "Not Wispr Flow — voice-to-text for macOS",
  description:
    "Free, offline voice-to-text menu bar app for macOS. Hold a key, speak, release — your words appear wherever your cursor is.",
  openGraph: {
    title: "Not Wispr Flow",
    description:
      "Free, offline voice-to-text for macOS. Hold a key, speak, release.",
    images: [{ url: "/og-card.png", width: 1200, height: 630 }],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/og-card.png"],
  },
  icons: {
    icon: [
      {
        url: "/logo-light-mode.png",
        type: "image/png",
        media: "(prefers-color-scheme: light)",
      },
      {
        url: "/logo-dark-mode.png",
        type: "image/png",
        media: "(prefers-color-scheme: dark)",
      },
    ],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${recoleta.variable} ${sans.variable} ${mono.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
