import type React from "react";
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { ThemeProvider } from "@/components/ThemeProvider";
import "./globals.css";
import Header from "@/components/header";
import clsx from "clsx";
import { SessionProvider } from "@/context/SessionContext";
import Link from "next/link";
import Image from "next/image";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

// SVG for the emoji favicon: 🏗️🇨🇦 using separate text elements, further reduced font
// and Unicode escape for the Canadian flag emoji.
const canadianFlagEmoji = "\u{1F1E8}\u{1F1E6}"; // 🇨🇦
const emojiFaviconSvg = `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>
    <text x='5' y='65' font-size='45'>🏗️</text>
    <text x='50' y='65' font-size='45'>${canadianFlagEmoji}</text>
  </svg>`;
// A bit of trial and error might be needed for x, y, and font-size
// to get them perfectly aligned and sized in the small favicon space.
// The y='72' and font-size='60' are estimations to make them fit side-by-side.

const faviconDataUrl = `data:image/svg+xml,${encodeURIComponent(emojiFaviconSvg)}`;

export const metadata: Metadata = {
  title: `Outcome Tracker - Build Canada 🏗️${canadianFlagEmoji}`,
  description: "Track the progress of Canada's government initiatives",
  icons: {
    icon: faviconDataUrl,
    // You could also specify other icon types if needed, e.g.:
    // apple: faviconDataUrl, // For Apple touch icon
    // shortcut: faviconDataUrl, // For older browsers
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${inter.className} text-neutral-800 dark:text-neutral-200 bg-background`}
      >
        <div className="border-2 border-black m-5">
          <ThemeProvider
            attribute="class"
            defaultTheme="light"
            enableSystem
            disableTransitionOnChange
          >
            <SessionProvider>
              <Header />
              <main className="container mx-auto p-4 bg-white dark:bg-neutral-900 site-main-content">
                {children}
              </main>

              {/* Footer styled to mimic buildcanada.com */}
              <footer
                className="mt-16 py-12 text-neutral-300 dark:text-neutral-400"
                style={{ backgroundColor: "#272727" }} // Directly using the dark footer color from example
              >
                <div className="container mx-auto text-center">
                  <div className="mb-8">
                    {/* The Build Canada logo can be used here too if desired, or just text */}
                    <h1 className="text-3xl font-semibold text-white">
                      Build Canada
                    </h1>
                  </div>
                  <div className="footprint">
                    <div className="copyright mb-6">
                      <div className="text-sm">
                        🏗️🇨🇦 ️Copyright Build Canada Inc. 2025
                      </div>
                    </div>
                    <div className="quote text-sm italic max-w-2xl mx-auto">
                      &quot;Whatever our errors are otherwise, we shall not err
                      for want of boldness... Canada shall be the star towards
                      which all men who love progress and freedom shall
                      come.&quot;
                      <div className="caption not-italic mt-2 text-xs">
                        — Laurier
                      </div>
                    </div>
                  </div>
                </div>
              </footer>
            </SessionProvider>
          </ThemeProvider>
        </div>
      </body>
    </html>
  );
}
