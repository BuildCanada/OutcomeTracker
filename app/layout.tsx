import type React from "react";
import type { Metadata } from "next";
import "./globals.css";
import Header from "@/components/header";
import { SessionProvider } from "@/context/SessionContext";
import { Toaster } from "@/components/ui/toaster";
import { SimpleAnalytics } from "@/components/SimpleAnalytics";
import Script from "next/script";
import SWRProvider from "@/components/SWRProvider";

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
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_BASE_URL || "https://buildcanada.com",
  ),
  title: `Outcomes Tracker - Build Canada 🏗️${canadianFlagEmoji}`,
  description: "Track the progress of Canada's government initiatives",
  icons: {
    icon: faviconDataUrl,
    // You could also specify other icon types if needed, e.g.:
    // apple: faviconDataUrl, // For Apple touch icon
    // shortcut: faviconDataUrl, // For older browsers
  },
  openGraph: {
    title: `Outcomes Tracker - Build Canada 🏗️${canadianFlagEmoji}`,
    description: "Track the progress of Canada's government initiatives",
    images: [
      {
        url: "/outcomes-tracker-seo-image.png",
        width: 1200,
        height: 630,
        alt: "Build Canada Outcomes Tracker",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: `Outcomes Tracker - Build Canada 🏗️${canadianFlagEmoji}`,
    description: "Track the progress of Canada's government initiatives",
    images: ["/outcomes-tracker-seo-image.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning className="bg-background">
      <body className={`text-neutral-800 bg-background`}>
        <div className="border-2 border-black m-5">
          <SessionProvider>
            <Header />
            <main className="container mx-auto bg-background site-main-content">
              <SWRProvider>{children}</SWRProvider>
            </main>

            {/* Footer styled to mimic buildcanada.com */}
            <footer
              className="mt-16 py-12 text-neutral-300"
              style={{ backgroundColor: "#272727" }}
            >
              <div className="container mx-auto">
                <div className="mb-8">
                  <h1 className="text-3xl font-semibold text-white">
                    Build Canada
                  </h1>
                </div>
                <div className="mb-8">
                  <p className="text-white">
                    A non-partisan platform tracking progress of key commitments
                    during the 45th Parliament of Canada.
                  </p>
                </div>
                <div className="footprint">
                  <div className="copyright text-white mb-6">
                    <div className="text-sm">🏗️🇨🇦 &copy; Build Canada 2025</div>
                  </div>
                </div>
              </div>
            </footer>
          </SessionProvider>
        </div>
        <Toaster />
        <SimpleAnalytics />
        <Script
          src="https://frenglish.ai/frenglish.bundle.js"
          strategy="beforeInteractive"
        />
        <Script id="frenglish-init" strategy="afterInteractive">
          {`
            window.frenglishSettings = {
              api_key: '26da1b6f351b6c9f2624c39b125322ac'
            };
            if (window.Frenglish) {
              window.Frenglish.initialize(window.frenglishSettings);
            }
          `}
        </Script>
      </body>
    </html>
  );
}
