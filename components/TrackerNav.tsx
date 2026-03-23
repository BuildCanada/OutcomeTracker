"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Overview" },
  { href: "/commitments", label: "Explore" },
  { href: "/faq", label: "FAQ" },
];

export default function TrackerNav() {
  const pathname = usePathname();

  return (
    <nav className="flex gap-2 mb-8">
      {NAV_ITEMS.map(({ href, label }) => {
        const active =
          href === "/"
            ? pathname === "/tracker" || pathname === "/tracker/"
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
  );
}
