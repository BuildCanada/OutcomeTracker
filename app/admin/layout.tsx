'use client'; // If using client-side components like Tabs from shadcn/ui directly

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation'; // To determine active tab
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'; // Assuming shadcn/ui tabs

// Re-using some styling constants from your main page for consistency
const DARK_BORDER_COLOR = "border-neutral-700";
const HEADER_BOTTOM_BORDER_COLOR = "border-neutral-400";
const NAV_LINK_TEXT_COLOR = "text-neutral-800";
const NAV_LINK_ACTIVE_TEXT_COLOR = "text-[#8b2332]";

interface AdminLayoutProps {
  children: React.ReactNode;
}

const adminTabs = [
  { name: 'Review Links', href: '/admin/reviews', id: 'reviews' },
  { name: 'Set Session', href: '/admin/settings', id: 'settings' }, // Path matches your current settings page
  // Add more admin tabs here as needed
];

export default function AdminLayout({ children }: AdminLayoutProps) {
  const pathname = usePathname();

  // Determine default active tab based on current path
  let defaultTabValue = 'reviews'; // Default to first tab
  const currentMainPath = pathname.split('/')[2]; // e.g., 'reviews' or 'settings'
  if (currentMainPath && adminTabs.some(tab => tab.id === currentMainPath)) {
    defaultTabValue = currentMainPath;
  }

  return (
    <div className="min-h-screen bg-[#f8f2ea] font-sans">
      {/* Main App Header (Simplified or Shared) */}
      <header className={`sticky top-0 z-50 bg-white shadow-sm ${HEADER_BOTTOM_BORDER_COLOR} border-b`}>
        <div className={`mx-auto flex max-w-7xl items-stretch`}>
          <div className={`bg-[#8b2332] p-4 flex items-center ${DARK_BORDER_COLOR} border-r`}>
            <Link href="/" className="text-xl font-bold text-white">Promise Tracker</Link>
          </div>
          <nav className="flex flex-1 items-stretch">
            <Link
              href="/"
              className={`flex items-center ${DARK_BORDER_COLOR} border-r px-6 py-4 text-sm font-medium uppercase tracking-wider ${NAV_LINK_TEXT_COLOR} hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-[#8b2332] transition-colors duration-150 ease-in-out md:px-8`}
            >
              Back to Main App
            </Link>
            {/* You can add other specific admin header links if needed */}
          </nav>
        </div>
      </header>

      {/* Admin Content Area */}
      <main className="container mx-auto max-w-5xl px-4 py-12">
        <h1 className="mb-8 text-3xl font-bold text-[#222222]">Promise Tracker Admin</h1>
        
        <Tabs defaultValue={defaultTabValue} className="w-full">
          <TabsList className="grid w-full grid-cols-2 mb-[-1px] border-b border-[#d3c7b9]">
            {adminTabs.map((tab) => (
              <Link key={tab.id} href={tab.href} passHref legacyBehavior>
                <TabsTrigger 
                  value={tab.id} 
                  className="flex-grow whitespace-normal h-auto flex items-center justify-center text-center border border-b-0 border-l-0 first:border-l border-[#d3c7b9] bg-white px-3 py-3 text-xs sm:text-sm uppercase tracking-wider data-[state=active]:bg-[#8b2332] data-[state=active]:text-white data-[state=active]:border-[#8b2332] data-[state=active]:border-b-transparent data-[state=active]:relative data-[state=active]:-mb-[1px] rounded-none rounded-t-md focus-visible:ring-offset-0 focus-visible:ring-2 focus-visible:ring-[#8b2332] focus:z-10 hover:bg-gray-50"
                >
                  {tab.name}
                </TabsTrigger>
              </Link>
            ))}
          </TabsList>
          {/* The content for each tab will be rendered by the respective page.tsx file via {children} */}
          <div className="border border-t-0 border-[#d3c7b9] bg-white p-6 rounded-b-md shadow-sm mt-0">
            {children}
          </div>
        </Tabs>
      </main>

      {/* Optional: Shared Footer */}
      {/* <footer className="py-8 text-center text-sm text-gray-500">
        Promise Tracker Admin Footer
      </footer> */}
    </div>
  );
} 