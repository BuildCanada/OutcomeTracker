import Link from "next/link"
import { usePathname } from 'next/navigation'

export default function Header() {
  const pathname = usePathname()

  return (
    <header className="border-b border-canada-red sticky top-0 z-50 bg-white shadow-sm">
      <div className="container mx-auto flex h-16 items-center justify-between px-4">
        <Link href="/" className="flex items-center gap-2">
          <div className="bg-canada-red text-white p-2 rounded">
            <span className="text-xl font-bold">🍁</span>
          </div>
          <span className="text-xl font-bold text-canada-red">Canada\'s Promise Tracker</span>
        </Link>
        <nav className="flex items-stretch gap-1">
          <Link
            href="/"
            className={`flex items-center px-3 py-2 text-sm font-medium border rounded-md \
              ${pathname === '/' 
                ? 'text-gray-900 bg-gray-100 border-gray-700' 
                : 'text-gray-700 hover:bg-gray-100 hover:text-gray-900 border-transparent hover:border-gray-300'}`}
          >
            Platform Tracker
          </Link>
          <Link
            href="/about"
            className={`flex items-center px-3 py-2 text-sm font-medium border rounded-md \
              ${pathname === '/about' 
                ? 'text-gray-900 bg-gray-100 border-gray-700' 
                : 'text-gray-700 hover:bg-gray-100 hover:text-gray-900 border-transparent hover:border-gray-300'}`}
          >
            About
          </Link>
        </nav>
      </div>
    </header>
  )
} 