import Link from "next/link"

export default function Header() {
  return (
    <header className="border-b border-canada-red">
      <div className="container mx-auto flex h-16 items-center justify-between px-4">
        <Link href="/" className="flex items-center gap-2">
          <div className="bg-canada-red text-white p-2 rounded">
            <span className="text-xl font-bold">🍁</span>
          </div>
          <span className="text-xl font-bold text-canada-red">Canada's Promise Tracker</span>
        </Link>
        <nav className="flex items-center gap-6">
          <Link href="/" className="text-sm font-medium hover:underline text-canada-red">
            Home
          </Link>
          <Link href="/about" className="text-sm font-medium hover:underline text-canada-red">
            About
          </Link>
        </nav>
      </div>
    </header>
  )
}
