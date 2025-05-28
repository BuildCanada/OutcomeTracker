'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import {
  collection, getDocs, doc, updateDoc, onSnapshot, DocumentData, Firestore
} from 'firebase/firestore';
import { db, firebaseApp } from '@/lib/firebase'; // Import shared instance

// --- Types ---
export interface ParliamentSession {
  id: string; // parliament_number, e.g., "44"
  parliament_number: string;
  session_label: string;
  start_date: string;
  end_date?: string | null;
  prime_minister_name?: string;
  governing_party?: string;
  election_date_preceding?: string | null;
  is_current_for_tracking?: boolean;
  notes?: string | null;
}

interface SessionContextType {
  sessions: ParliamentSession[];
  currentSessionId: string | null;
  isLoadingSessions: boolean;
  isLoadingCurrentSession: boolean;
  error: string | null;
  setCurrentSessionIdAndUpdateGlobal: (newSessionId: string) => Promise<void>;
}

const SessionContext = createContext<SessionContextType | undefined>(undefined);

interface SessionProviderProps {
  children: ReactNode;
}

export const SessionProvider: React.FC<SessionProviderProps> = ({ children }) => {
  const [sessions, setSessions] = useState<ParliamentSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [isLoadingSessions, setIsLoadingSessions] = useState<boolean>(true);
  const [isLoadingCurrentSession, setIsLoadingCurrentSession] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch all available parliamentary sessions and current session from global config
  useEffect(() => {
    if (!db) {
      setError("Firestore not initialized. Ensure @/lib/firebase is configured correctly.");
      setIsLoadingSessions(false);
      return;
    }
    const fetchSessionsAndCurrentConfig = async () => {
      setIsLoadingSessions(true);
      setError(null);
      try {
        if (!db) {
            setError("Firestore instance is not available after initial check.");
            setIsLoadingSessions(false);
            return;
        }
        
        // Fetch all sessions
        const sessionsCollection = collection(db, 'parliament_session');
        const snapshot = await getDocs(sessionsCollection);
        const fetchedSessions: ParliamentSession[] = snapshot.docs.map(docSnap => ({
          id: docSnap.id,
          ...docSnap.data(),
        } as ParliamentSession));
        // Sort by parliament_number descending (e.g., 45, 44, 43)
        fetchedSessions.sort((a, b) => parseInt(b.parliament_number, 10) - parseInt(a.parliament_number, 10));
        setSessions(fetchedSessions);
        
        // Get current session from API endpoint instead of direct Firestore access
        try {
          const response = await fetch('/api/admin/current-session');
          if (response.ok) {
            const data = await response.json();
            if (data.success && data.currentSessionId) {
              setCurrentSessionId(data.currentSessionId);
              console.log(`[SessionContext] Loaded current session from API: ${data.currentSessionId}`);
            } else {
              // Fallback to the session marked as current_for_tracking
              const currentSession = fetchedSessions.find(session => session.is_current_for_tracking);
              if (currentSession) {
                setCurrentSessionId(currentSession.id);
                console.log(`[SessionContext] Fallback to is_current_for_tracking session: ${currentSession.id}`);
              } else if (fetchedSessions.length > 0) {
                // Final fallback to the most recent session
                setCurrentSessionId(fetchedSessions[0].id);
                console.log(`[SessionContext] Final fallback to most recent session: ${fetchedSessions[0].id}`);
              }
            }
          } else {
            throw new Error(`API request failed: ${response.statusText}`);
          }
        } catch (apiError: any) {
          console.warn("[SessionContext] Error fetching current session from API, using fallback:", apiError);
          // Fallback to the session marked as current_for_tracking
          const currentSession = fetchedSessions.find(session => session.is_current_for_tracking);
          if (currentSession) {
            setCurrentSessionId(currentSession.id);
          } else if (fetchedSessions.length > 0) {
            // Final fallback to the most recent session
            setCurrentSessionId(fetchedSessions[0].id);
          }
        }
      } catch (e: any) {
        console.error("Error fetching sessions:", e);
        setError(`Failed to fetch sessions: ${e.message}`);
      }
      setIsLoadingSessions(false);
    };
    fetchSessionsAndCurrentConfig();
  }, []);

  // Function to update the current session ID and persist to global config
  const setCurrentSessionIdAndUpdateGlobal = useCallback(async (newSessionId: string) => {
    if (!newSessionId) {
        setError("Cannot set an empty session ID.");
        return;
    }
    
    setIsLoadingCurrentSession(true);
    setError(null);
    
    try {
      // Call the API to update the global config
      const response = await fetch('/api/admin/settings', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          current_selected_parliament_session: newSessionId
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `Failed to update session: ${response.statusText}`);
      }

      // Update the client-side state only after successful API call
      setCurrentSessionId(newSessionId);
      console.log(`[SessionContext] Session successfully updated to: ${newSessionId}`);
      
    } catch (e: any) {
      console.error("[SessionContext] Error updating session:", e);
      setError(`Failed to update session: ${e.message}`);
    } finally {
      setIsLoadingCurrentSession(false);
    }
  }, []);

  return (
    <SessionContext.Provider value={{
      sessions,
      currentSessionId,
      isLoadingSessions,
      isLoadingCurrentSession,
      error,
      setCurrentSessionIdAndUpdateGlobal
    }}>
      {children}
    </SessionContext.Provider>
  );
};

export const useSession = (): SessionContextType => {
  const context = useContext(SessionContext);
  if (context === undefined) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return context;
}; 