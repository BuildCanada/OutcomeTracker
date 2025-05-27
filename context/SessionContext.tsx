'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import {
  collection, getDocs, doc, getDoc, updateDoc, onSnapshot, DocumentData, Firestore
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

  // Fetch all available parliamentary sessions
  useEffect(() => {
    if (!db) {
      setError("Firestore not initialized. Ensure @/lib/firebase is configured correctly.");
      setIsLoadingSessions(false);
      return;
    }
    const fetchSessions = async () => {
      setIsLoadingSessions(true);
      setError(null);
      try {
        if (!db) {
            setError("Firestore instance is not available after initial check.");
            setIsLoadingSessions(false);
            return;
        }
        const sessionsCollection = collection(db, 'parliament_session');
        const snapshot = await getDocs(sessionsCollection);
        const fetchedSessions: ParliamentSession[] = snapshot.docs.map(docSnap => ({
          id: docSnap.id,
          ...docSnap.data(),
        } as ParliamentSession));
        // Sort by parliament_number descending (e.g., 45, 44, 43)
        fetchedSessions.sort((a, b) => parseInt(b.parliament_number, 10) - parseInt(a.parliament_number, 10));
        setSessions(fetchedSessions);
        
        // Set the current session to the one marked as current_for_tracking
        const currentSession = fetchedSessions.find(session => session.is_current_for_tracking);
        if (currentSession) {
          setCurrentSessionId(currentSession.id);
        } else if (fetchedSessions.length > 0) {
          // Fallback to the most recent session
          setCurrentSessionId(fetchedSessions[0].id);
        }
      } catch (e: any) {
        console.error("Error fetching sessions:", e);
        setError(`Failed to fetch sessions: ${e.message}`);
      }
      setIsLoadingSessions(false);
    };
    fetchSessions();
  }, []);

  // Function to update the current session ID (client-side only for now)
  const setCurrentSessionIdAndUpdateGlobal = useCallback(async (newSessionId: string) => {
    if (!newSessionId) {
        setError("Cannot set an empty session ID.");
        return;
    }
    setError(null);
    // For now, just update the client-side state
    // TODO: Implement server-side API to update admin settings
    setCurrentSessionId(newSessionId);
    console.log(`Session updated to: ${newSessionId}`);
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