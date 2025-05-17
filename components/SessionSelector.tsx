'use client';

import React from 'react';
import { useSession } from '@/context/SessionContext';

const SessionSelector: React.FC = () => {
  const {
    sessions,
    currentSessionId,
    isLoadingSessions,
    isLoadingCurrentSession,
    error,
    setCurrentSessionIdAndUpdateGlobal
  } = useSession();

  const handleSessionChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const newSessionId = event.target.value;
    if (newSessionId) {
      setCurrentSessionIdAndUpdateGlobal(newSessionId);
    }
  };

  if (isLoadingSessions || isLoadingCurrentSession) {
    return <div className="p-2 text-sm text-gray-500">Loading sessions...</div>;
  }

  if (error) {
    return <div className="p-2 text-sm text-red-500">Error: {error}</div>;
  }

  if (!sessions.length) {
    return <div className="p-2 text-sm text-gray-500">No parliamentary sessions available.</div>;
  }

  return (
    <div className="p-2 bg-gray-100 dark:bg-gray-800 rounded-md shadow">
      <label htmlFor="session-selector" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
        Parliamentary Session:
      </label>
      <select
        id="session-selector"
        value={currentSessionId || ''} // Ensure value is controlled, fallback to empty string if null
        onChange={handleSessionChange}
        className="block w-full pl-3 pr-10 py-2 text-base border-gray-300 dark:border-gray-600 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
        disabled={isLoadingSessions || isLoadingCurrentSession}
      >
        {currentSessionId === null && !isLoadingCurrentSession && <option value="" disabled>Select a session</option>}
        {sessions.map((session) => (
          <option key={session.id} value={session.parliament_number}>
            {session.session_label} (Parl: {session.parliament_number})
          </option>
        ))}
      </select>
      {/* Display a subtle loading indicator when changing session perhaps, or rely on dropdown disabled state */}
    </div>
  );
};

export default SessionSelector; 