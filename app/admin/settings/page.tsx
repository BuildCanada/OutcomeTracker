"use client"; // Or remove if SessionSelector can be part of a server component structure

import SessionSelector from "@/components/SessionSelector";
import { useSession } from "@/context/SessionContext"; // To display current session or errors

export default function AdminSettingsPage() {
  const { currentSessionId, isLoadingCurrentSession, error } = useSession();

  return (
    // <div className="container mx-auto p-4"> // Container and padding now handled by layout
    //   <h1 className="text-2xl font-semibold mb-6">Admin Settings</h1> // Heading removed, handled by layout/tabs
      
      <div className="mb-8 pt-2">
        {/* Optional: Add a sub-heading if needed, e.g. <h2 className="text-xl font-medium mb-4">Session Configuration</h2> */}
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
          Select the active parliamentary session for the application. This setting affects data displayed and ingested across the platform.
        </p>
        <SessionSelector />
        {isLoadingCurrentSession && <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">Loading current session...</p>}
        {error && <p className="mt-2 text-sm text-red-500">Session context error: {error}</p>}
        {currentSessionId && !isLoadingCurrentSession && (
          <p className="mt-3 text-sm text-gray-700 dark:text-gray-300">
            Currently selected session ID for tracking: <strong>{currentSessionId}</strong>
          </p>
        )}
      </div>
    // </div>
  );
} 