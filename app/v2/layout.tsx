"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/v2", label: "Overview" },
  { href: "/v2/platform", label: "Platform" },
  { href: "/v2/commitments", label: "Explore" },
  { href: "/v2/feed", label: "Feed" },
];

export default function V2Layout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div>
      <nav className="flex gap-2 mb-8">
        {NAV_ITEMS.map(({ href, label }) => {
          const active =
            href === "/v2"
              ? pathname === "/tracker/v2"
              : pathname?.startsWith(`/tracker${href}`);
          return (
            <Link
              key={href}
              href={href}
              className={`px-4 py-2 text-sm font-mono transition-colors ${
                active
                  ? "bg-[#8b2332] text-white"
                  : "bg-white text-[#222222] border border-[#d3c7b9] hover:bg-gray-50"
              }`}
            >
              {label}
            </Link>
          );
        })}
      </nav>
      {children}
    </div>
  );
}
