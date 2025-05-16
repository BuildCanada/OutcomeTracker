import type React from "react";
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { ThemeProvider } from "@/components/theme-provider";
import "./globals.css";
import Header from "@/components/header";

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
  title: `Build Canada 🏗️${canadianFlagEmoji}`,
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
      <body className={inter.className}>
        <ThemeProvider
          attribute="class"
          defaultTheme="light"
          enableSystem
          disableTransitionOnChange
        >
          <div className="border-2 border-black m-5">
            <Header />
            {children}
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}
