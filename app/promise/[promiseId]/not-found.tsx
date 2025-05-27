import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ArrowLeftIcon, SearchIcon } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="max-w-md w-full text-center">
        <div className="mb-8">
          <SearchIcon className="mx-auto h-16 w-16 text-gray-400" />
        </div>
        
        <h1 className="text-3xl font-bold text-gray-900 mb-4">
          Promise Not Found
        </h1>
        
        <p className="text-gray-600 mb-8">
          The promise you're looking for doesn't exist or may have been moved. 
          Please check the URL or return to the main tracker.
        </p>
        
        <div className="space-y-4">
          <Link href="/en/tracker">
            <Button className="w-full bg-[#8b2332] hover:bg-[#7a1f2b] text-white">
              <ArrowLeftIcon className="mr-2 h-4 w-4" />
              Back to Promise Tracker
            </Button>
          </Link>
          
          <Link href="/">
            <Button variant="outline" className="w-full">
              Go to Homepage
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
} 