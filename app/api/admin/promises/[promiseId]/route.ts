import { NextRequest, NextResponse } from 'next/server';
import { firestoreAdmin } from '@/lib/firebaseAdmin';
import { FieldValue } from 'firebase-admin/firestore';

interface PromiseUpdateData {
  text?: string;
  source_type?: string;
  bc_promise_rank?: 'strong' | 'medium' | 'weak' | null;
  bc_promise_direction?: string | null;
  bc_promise_rank_rationale?: string | null;
  department?: string;
  status?: string;
  // Allow other fields that might be part of the promise document
  [key: string]: any;
}

export async function PUT(
  request: NextRequest,
  { params }: { params: { promiseId: string } }
) {
  // TODO: Implement robust authentication and authorization here
  // For example, check if the user is an admin
  // if (!isAdmin(request)) { 
  //   return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  // }

  const { promiseId } = params;
  if (!promiseId) {
    return NextResponse.json({ error: 'Promise ID is required' }, { status: 400 });
  }

  try {
    const body = await request.json();
    const updateData: PromiseUpdateData = body;

    // Firestore collection path - FIXME: Hardcoded for LPC in Canada
    const collectionPath = 'promises/Canada/LPC';
    const promiseRef = firestoreAdmin.collection(collectionPath).doc(promiseId);

    // Prepare data for Firestore, ensuring nulls are handled correctly
    // Firestore update doesn't create fields if value is undefined.
    // To explicitly set a field to null, we pass null.
    const firestoreUpdateData: { [key: string]: any } = {};
    for (const key in updateData) {
      if (Object.prototype.hasOwnProperty.call(updateData, key)) {
        // If a field intended to be nullable (like bc_promise_rank) is an empty string from form, convert to null
        if ((key === 'bc_promise_rank' || key === 'bc_promise_direction' || key === 'bc_promise_rank_rationale') && updateData[key] === '') {
          firestoreUpdateData[key] = null;
        } else if (updateData[key] === undefined) {
           // If a key exists but is undefined, we might want to remove it or set to null.
           // For `update`, undefined means no change. To remove a field, use FieldValue.delete().
           // For now, we only pass defined values or explicit nulls.
           // If you want to allow field deletion, that needs specific handling.
        }
        else {
          firestoreUpdateData[key] = updateData[key];
        }
      }
    }
    
    // Add a timestamp for the last update
    firestoreUpdateData.last_updated_admin = FieldValue.serverTimestamp();


    await promiseRef.update(firestoreUpdateData);

    return NextResponse.json({ message: 'Promise updated successfully', id: promiseId }, { status: 200 });

  } catch (error: any) {
    console.error(`Error updating promise ${promiseId}:`, error);
    let errorMessage = 'Internal server error';
    if (error.code === 'NOT_FOUND') {
      errorMessage = 'Promise not found';
      return NextResponse.json({ error: errorMessage, details: error.message }, { status: 404 });
    }
    if (typeof error === 'object' && error !== null && 'message' in error) {
        errorMessage = (error as {message: string}).message;
    }
    return NextResponse.json({ error: 'Failed to update promise.', details: errorMessage }, { status: 500 });
  }
} 