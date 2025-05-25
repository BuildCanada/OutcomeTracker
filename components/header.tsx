import Link from "next/link";

export default function Header({ lang = "en" }: { lang?: "fr" | "en" }) {
  return (
    <header className="border-b-2 border-black font-founders bg-background sticky top-0 z-50">
      <div className="mx-auto grid grid-cols-[160px_1fr] min-h-[72px]">
        <div className="bg-[#932f2f] flex items-center justify-center">
          <Link href="/" className="block">
            <img
              src="https://cdn.prod.website-files.com/679d23fc682f2bf860558c9a/679d23fc682f2bf860558cc6_build_canada-wordmark.svg"
              alt="Build Canada"
              className="w-[110px] h-auto p-2"
            />
          </Link>
        </div>
        <nav className="grid grid-cols-4 divide-x-2 divide-black">
          <Link
            href="/memos"
            className="flex items-center justify-center text-[16px] tracking-wide uppercase hover:bg-[#eae0d8]"
          >
            Memos
          </Link>
          <Link
            // TODO: Make this dynamic based on language
            href="/en/tracker"
            className="flex items-center justify-center text-[16px] tracking-wide uppercase hover:bg-[#eae0d8]"
          >
            Promise Tracker
          </Link>
          <Link
            href="/about"
            className="flex items-center justify-center text-[16px] tracking-wide uppercase hover:bg-[#eae0d8]"
          >
            About
          </Link>
          <Link
            href="/contact"
            className="flex items-center justify-center text-[16px] tracking-wide uppercase hover:bg-[#eae0d8]"
          >
            Contact
          </Link>
        </nav>
      </div>
    </header>
  );
}
