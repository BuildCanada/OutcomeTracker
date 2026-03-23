import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-20">
      <h2 className="text-2xl font-bold mb-2">Page Not Found</h2>
      <p className="text-gray-500 mb-4">
        The page you are looking for does not exist.
      </p>
      <Link href="/" className="text-[#8b2332] hover:underline">
        Go to Overview
      </Link>
    </div>
  );
}
