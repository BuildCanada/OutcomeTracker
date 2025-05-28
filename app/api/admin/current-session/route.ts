import { NextRequest, NextResponse } from 'next/server';
import { firestoreAdmin } from '@/lib/firebaseAdmin';

export async function GET(request: NextRequest) {
  try {
    // Get current session from global config
    const globalConfigDoc = await firestoreAdmin.doc('admin_settings/global_config').get();
    
    let currentSessionId: string | null = null;
    
    if (globalConfigDoc.exists && globalConfigDoc.data()?.current_selected_parliament_session) {
      currentSessionId = String(globalConfigDoc.data()?.current_selected_parliament_session);
    } else {
      // Fallback to the session marked as current_for_tracking
      const fallbackSessionQuery = await firestoreAdmin.collection('parliament_session')
        .where('is_current_for_tracking', '==', true)
        .limit(1)
        .get();
      
      if (!fallbackSessionQuery.empty) {
        currentSessionId = fallbackSessionQuery.docs[0].id;
      } else {
        // Final fallback to the most recent session (highest parliament_number)
        const recentSessionQuery = await firestoreAdmin.collection('parliament_session')
          .orderBy('parliament_number', 'desc')
          .limit(1)
          .get();
        
        if (!recentSessionQuery.empty) {
          currentSessionId = recentSessionQuery.docs[0].id;
        }
      }
    }

    return NextResponse.json({ 
      currentSessionId,
      success: true 
    }, { status: 200 });

  } catch (error: any) {
    console.error('Error fetching current session:', error);
    let errorMessage = 'Internal server error';
    if (typeof error === 'object' && error !== null && 'message' in error) {
      errorMessage = (error as {message: string}).message;
    }
    return NextResponse.json({ 
      error: 'Failed to fetch current session.', 
      details: errorMessage,
      currentSessionId: null,
      success: false
    }, { status: 500 });
  }
} 