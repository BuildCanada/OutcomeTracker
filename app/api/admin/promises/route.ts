import { NextRequest, NextResponse } from 'next/server';
import { firestoreAdmin } from '@/lib/firebaseAdmin';
import { DocumentData, Query } from 'firebase-admin/firestore';

// Define the expected shape of a promise, similar to the frontend
interface PromiseData {
  id: string;
  text: string;
  source_type: string;
  bc_promise_rank?: 'strong' | 'medium' | 'weak' | null;
  parliament_session_id?: string;
  // Include other fields that might be stored and returned
  [key: string]: any;
}

export async function GET(request: NextRequest) {
  // TODO: Implement robust authentication and authorization here
  // For example, check if the user is an admin
  // if (!isAdmin(request)) { 
  //   return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  // }

  const { searchParams } = new URL(request.url);
  const source_type = searchParams.get('source_type');
  const bc_promise_rank = searchParams.get('bc_promise_rank');
  const parliament_session_id = searchParams.get('parliament_session_id');
  const searchText = searchParams.get('searchText'); // Client-side search will use this later on fetched data
  const limitParam = searchParams.get('limit');
  const pageParam = searchParams.get('page'); // For pagination, if implemented later

  // Using flat promises collection structure
  const collectionPath = 'promises';
  let query: Query<DocumentData> = firestoreAdmin.collection(collectionPath);
  let countQuery: Query<DocumentData> = firestoreAdmin.collection(collectionPath); // Separate query for counting

  // Apply filters for flat structure - hardcoded for LPC in Canada for now
  query = query.where('party_code', '==', 'LPC').where('region_code', '==', 'Canada');
  countQuery = countQuery.where('party_code', '==', 'LPC').where('region_code', '==', 'Canada');

  // Filter by parliament session if provided
  if (parliament_session_id) {
    query = query.where('parliament_session_id', '==', parliament_session_id);
    countQuery = countQuery.where('parliament_session_id', '==', parliament_session_id);
  }

  // Apply filters using tuple syntax for .where()
  if (source_type && source_type !== 'all') {
    query = query.where('source_type', '==', source_type);
    countQuery = countQuery.where('source_type', '==', source_type);
  }

  if (bc_promise_rank && bc_promise_rank !== 'all') {
    if (bc_promise_rank === 'none') {
      query = query.where('bc_promise_rank', '==', null);
      countQuery = countQuery.where('bc_promise_rank', '==', null);
    } else {
      query = query.where('bc_promise_rank', '==', bc_promise_rank);
      countQuery = countQuery.where('bc_promise_rank', '==', bc_promise_rank);
    }
  }

  // Note: searchText is applied client-side in the frontend after this API call returns data.
  // So, the total count from Firestore should reflect the filters applied here (source_type, bc_promise_rank)
  // and not be affected by client-side searchText.

  try {
    // Get the total count of documents matching the filters (before limit)
    const countSnapshot = await countQuery.count().get();
    const totalRecords = countSnapshot.data().count;

    const defaultLimit = 25;
    let queryLimit = limitParam ? parseInt(limitParam) : defaultLimit;
    if (isNaN(queryLimit) || queryLimit <= 0) {
      queryLimit = defaultLimit;
    }
    query = query.limit(queryLimit);
    // query = query.orderBy('text'); // Optional: Add consistent ordering if needed

    const snapshot = await query.get();
    const promises: PromiseData[] = snapshot.docs.map(doc => {
      const data = doc.data() as DocumentData;
      return {
        id: doc.id,
        text: data.text || '',
        source_type: data.source_type || '',
        bc_promise_rank: data.bc_promise_rank === undefined ? null : data.bc_promise_rank,
        parliament_session_id: data.parliament_session_id || undefined,
        ...data,
      } as PromiseData;
    });

    // Client-side text filtering is NOT done here in the API anymore for total count accuracy.
    // It's handled by the frontend on the `promises` array received.

    return NextResponse.json({ promises, total: totalRecords }, { status: 200 });

  } catch (error) {
    console.error('Error fetching promises:', error);
    const message = (typeof error === 'object' && error !== null && 'message' in error) ? (error as { message: string }).message : 'Internal server error';
    return NextResponse.json({ error: 'Failed to fetch promises.', details: message }, { status: 500 });
  }
}

// Placeholder for future PUT/POST/DELETE methods if needed in this specific route file
// For updating a single promise, a dynamic route like /api/admin/promises/[promiseId]/route.ts is more RESTful. 