'use client';

import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ListChecks, Settings, Archive, Activity } from 'lucide-react'; // Icons

export default function AdminHomePage() {
  const adminSections = [
    {
      id: 'reviews',
      href: '/admin/reviews',
      title: 'Review Evidence Links',
      description: 'Approve or reject pending evidence links submitted by users or automated processes.',
      icon: <ListChecks className="mb-4 h-12 w-12 text-[#8b2332]" />,
    },
    {
      id: 'promises',
      href: '/admin/promises',
      title: 'Manage Promises',
      description: 'Search, view, and edit promise details. Add new evidence directly to promises.',
      icon: <Archive className="mb-4 h-12 w-12 text-[#8b2332]" />,
    },
    {
      id: 'monitoring',
      href: '/admin/monitoring',
      title: 'RSS Monitoring',
      description: 'Monitor RSS feeds, data ingestion pipelines, and system health with real-time analytics and alerts.',
      icon: <Activity className="mb-4 h-12 w-12 text-[#8b2332]" />,
    },
    {
      id: 'settings',
      href: '/admin/settings',
      title: 'Application Settings',
      description: 'Configure global application settings, such as the active parliamentary session.',
      icon: <Settings className="mb-4 h-12 w-12 text-[#8b2332]" />,
    },
  ];

  return (
    <div>
      <div className="mb-8 text-center">
        <h2 className="text-2xl font-semibold text-gray-800">Admin Dashboard</h2>
        <p className="text-gray-600">Select an administrative task to continue.</p>
      </div>
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
        {adminSections.map((section) => (
          <Link href={section.href} key={section.id} passHref>
            <Card className="flex h-full transform flex-col overflow-hidden rounded-lg bg-white shadow-lg transition-all duration-300 ease-in-out hover:scale-105 hover:shadow-xl">
              <CardHeader className="items-center text-center">
                {section.icon}
                <CardTitle className="text-xl font-semibold text-[#333]">
                  {section.title}
                </CardTitle>
              </CardHeader>
              <CardContent className="flex-grow">
                <CardDescription className="text-center text-sm text-gray-600">
                  {section.description}
                </CardDescription>
              </CardContent>
              <div className="p-6 pt-0 text-center">
                <Button variant="outline" className="border-[#8b2332] text-[#8b2332] hover:bg-[#8b2332] hover:text-white">
                  Go to {section.title}
                </Button>
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
} 