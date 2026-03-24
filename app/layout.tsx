import type React from "react";
import type { Metadata } from "next";
import "./globals.css";
import { LazyToaster } from "@/components/LazyToaster";
import { SimpleAnalytics } from "@/components/SimpleAnalytics";
import SWRProvider from "@/components/SWRProvider";
import { Sidebar } from "@/components/HomePageClient";
import TrackerNav from "@/components/TrackerNav";

const title = "Outcomes Tracker - Build Canada";
const description = "Track the progress of Canada's government initiatives";
export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_BASE_URL || "https://buildcanada.com",
  ),
  title,
  description,
  icons: {
    icon: "/tracker/buildcanada-logo-square.svg",
    apple: "/tracker/buildcanada-logo-square.svg",
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
        <div className="lg:border-2 lg:border-black lg:m-5">
          <main className="bg-background site-main-content">
            <SWRProvider>
              <div className="min-h-screen">
                <div className="max-[385px]:px-1 px-2 py-3 lg:px-4 lg:py-6">
                  <div className="grid grid-cols-1 lg:grid-cols-4 lg:gap-6">
                    <Sidebar pageTitle="Outcomes Tracker" />
                    <div className="col-span-3">
                      <TrackerNav />
                      {children}
                    </div>
                  </div>
                </div>
              </div>
            </SWRProvider>
          </main>

          <footer
            className="mt-16 px-4 py-8 text-neutral-300"
            style={{ backgroundColor: "#272727" }}
          >
            <div className="container mx-auto">
              <div className="mb-8">
                <p className="text-white">
                  🏗️🇨🇦 A{" "}
                  <a href="/" className="underline decoration-white">
                    Build Canada
                  </a>{" "}
                  project.
                </p>
              </div>
            </div>
          </footer>
        </div>
        <LazyToaster />
        <SimpleAnalytics />
      </body>
    </html>
  );
}
