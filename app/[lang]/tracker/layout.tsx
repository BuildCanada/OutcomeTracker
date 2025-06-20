"use client";
import { DepartmentPillLinks, Sidebar } from "@/components/HomePageClient";

export default function Layout({
  children,
}: Readonly<{
  children: React.ReactNode;
  params: { lang: string; department?: string };
}>) {
  return (
    <div className="min-h-screen">
      <div className="container px-4 py-12">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <Sidebar pageTitle="Outcomes Tracker" />
          <div className="col-span-3">
            <DepartmentPillLinks />
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}