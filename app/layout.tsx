import type React from "react";
import type { Metadata } from "next";
import "./globals.css";
import Header from "@/components/header";
import { Toaster } from "@/components/ui/toaster";
import { SimpleAnalytics } from "@/components/SimpleAnalytics";
import Script from "next/script";
import SWRProvider from "@/components/SWRProvider";
import { DEPARTMENTS } from "./[department]/_constants";
import Link from "next/link";
import { Sidebar } from "@/components/HomePageClient";

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
const title = `Outcomes Tracker - Build Canada 🏗️${canadianFlagEmoji}`;
const description = "Track the progress of Canada's government initiatives";
export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_BASE_URL || "https://buildcanada.com",
  ),
  title,
  description,
  icons: {
    icon: faviconDataUrl,
    // You could also specify other icon types if needed, e.g.:
    // apple: faviconDataUrl, // For Apple touch icon
    // shortcut: faviconDataUrl, // For older browsers
  },
  openGraph: {
    title,
    description,
    images: [
      {
        url: "/tracker/outcomes-tracker-seo-image.png",
        width: 1200,
        height: 630,
        alt: "Build Canada Outcomes Tracker",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
    images: ["/tracker/outcomes-tracker-seo-image.png"],
  },
};

export default function RootLayout({
  children,
  params: { department },
}: Readonly<{
  children: React.ReactNode;
  params: { department?: string };
}>) {
  return (
    <html lang="en" suppressHydrationWarning className="bg-background">
      <body className={`text-neutral-800 bg-background`}>
        <div className="border-2 border-black m-5">
          <Header />
          <main className="container mx-auto bg-background site-main-content">
            <SWRProvider>
              <div className="min-h-screen">
                <div className="container px-4 py-12">
                  <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                    <Sidebar pageTitle="Outcomes Tracker" />
                    <div className="col-span-3">{children}</div>
                  </div>
                </div>
              </div>
            </SWRProvider>
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
        </div>
        <Toaster />
        <SimpleAnalytics />
        {/* <Script
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
        </Script> */}
      </body>
    </html>
  );
}
