'use client'; // If using client-side components like Tabs from shadcn/ui directly

import React from 'react';
import Link from 'next/link';
import { useRouter, usePathname } from 'next/navigation';

// Re-using some styling constants from your main page for consistency
const DARK_BORDER_COLOR = "border-neutral-700";
const HEADER_BOTTOM_BORDER_COLOR = "border-neutral-400";
const NAV_LINK_TEXT_COLOR = "text-neutral-800";

interface AdminLayoutProps {
  children: React.ReactNode;
}

export default function AdminLayout({ children }: AdminLayoutProps) {
  const router = useRouter();
  const pathname = usePathname();

  const handleLogout = async () => {
    try {
      await fetch('/api/admin/auth', {
        method: 'DELETE',
      });
      router.push('/admin/login');
      router.refresh();
    } catch (error) {
      console.error('Logout error:', error);
    }
  };

  // Helper function to check if a link is active
  const isActiveLink = (href: string) => {
    if (href === '/admin') {
      return pathname === '/admin';
    }
    return pathname.startsWith(href);
  };

  // Admin navigation tabs with Back to Main App and Logout
  const adminTabs = [
    { href: '/admin', label: 'Dashboard', type: 'link' },
    { href: '/admin/evidence', label: 'Evidence', type: 'link' },
    { href: '/admin/promises', label: 'Promises', type: 'link' },
    { href: '/admin/monitoring', label: 'Monitoring', type: 'link' },
    { href: '/admin/settings', label: 'Settings', type: 'link' },
    { href: '/en/tracker', label: 'Back to Main App', type: 'link' },
    { href: '#', label: 'Logout', type: 'button' }
  ];

  return (
    <div className="min-h-screen">
      {/* Consolidated Admin Header */}
      <header className={`sticky top-0 z-50 bg-white shadow-sm ${HEADER_BOTTOM_BORDER_COLOR} border-b`}>
        {/* Navigation Tabs */}
        <div className="bg-white">
          <div className="px-6">
            <nav className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <div className="bg-[#8b2332] px-3 py-1 rounded text-white text-sm font-medium mr-6">
                  Admin Dashboard
                </div>
                <div className="flex space-x-8">
                  {adminTabs.slice(0, -2).map((tab) => {
                    const isActive = isActiveLink(tab.href);
                    return (
                      <Link
                        key={tab.href}
                        href={tab.href}
                        className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors duration-150 ${
                          isActive
                            ? 'border-[#8b2332] text-[#8b2332]'
                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                        }`}
                      >
                        {tab.label}
                      </Link>
                    );
                  })}
                </div>
              </div>
              
              <div className="flex items-center space-x-8">
                <Link
                  href="/en/tracker"
                  className="py-4 px-1 border-b-2 border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 font-medium text-sm transition-colors duration-150"
                >
                  Back to Main App
                </Link>
                <button
                  onClick={handleLogout}
                  className="py-4 px-1 border-b-2 border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 font-medium text-sm transition-colors duration-150"
                >
                  Logout
                </button>
              </div>
            </nav>
          </div>
        </div>
      </header>

      {/* Admin Content Area - Full width */}
      <main className="min-h-screen bg-gray-50">
        <div className="p-6">
            {children}
        </div>
      </main>

    </div>
  );
} 