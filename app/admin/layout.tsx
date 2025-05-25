'use client'; // If using client-side components like Tabs from shadcn/ui directly

import React from 'react';
import Link from 'next/link';

// Re-using some styling constants from your main page for consistency
const DARK_BORDER_COLOR = "border-neutral-700";
const HEADER_BOTTOM_BORDER_COLOR = "border-neutral-400";
const NAV_LINK_TEXT_COLOR = "text-neutral-800";

interface AdminLayoutProps {
  children: React.ReactNode;
}


export default function AdminLayout({ children }: AdminLayoutProps) {


  return (
    <div className="min-h-screen font-financier">
      {/* Main App Header */}
      <header className={`sticky top-0 z-50 bg-white shadow-sm ${HEADER_BOTTOM_BORDER_COLOR} border-b`}>
        <div className={`mx-auto flex max-w-7xl items-stretch`}>
          <div className={`bg-[#8b2332] p-4 flex items-center ${DARK_BORDER_COLOR} border-r`}>
            {/* Updated Link to point to /admin and text changed */}
            <Link href="/admin" className="text-xl font-medium text-white">Admin Dashboard</Link>
          </div>
          <nav className="flex flex-1 items-stretch">
            <Link
              href="/admin/monitoring" 
              className={`flex items-center ${DARK_BORDER_COLOR} border-r px-6 py-4 text-sm font-medium tracking-wider ${NAV_LINK_TEXT_COLOR} hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-[#8b2332] transition-colors duration-150 ease-in-out md:px-8`}
            >
              RSS Monitoring
            </Link>
            <Link
              href="/en/tracker" 
              className={`flex items-center ${DARK_BORDER_COLOR} border-r px-6 py-4 text-sm font-medium tracking-wider ${NAV_LINK_TEXT_COLOR} hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-[#8b2332] transition-colors duration-150 ease-in-out md:px-8`}
            >
              Back to Main App
            </Link>
          </nav>
        </div>
      </header>

      {/* Admin Content Area */}
      <main className="container mx-auto max-w-5xl px-4 py-12">
        <div className="bg-white p-6 shadow-sm border border-[#d3c7b9]">
            {children}
        </div>
      </main>

    </div>
  );
} 