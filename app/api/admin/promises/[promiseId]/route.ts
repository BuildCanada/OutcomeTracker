import { NextRequest, NextResponse } from 'next/server';
import { firestoreAdmin } from '@/lib/firebaseAdmin';
import { FieldValue } from 'firebase-admin/firestore';

interface PromiseUpdateData {
  text?: string;
  source_type?: string;
  bc_promise_rank?: 'strong' | 'medium' | 'weak' | null;
  bc_promise_direction?: string | null;
  bc_promise_rank_rationale?: string | null;
  responsible_department_lead?: string;
  reporting_lead_title?: string;
  category?: string;
  date_issued?: string;
  progress_score?: number;
  progress_summary?: string;
  concise_title?: string;
  description?: string;
  what_it_means_for_canadians?: string;
  intended_impact_and_objectives?: string;
  background_and_context?: string;
  parliament_session_id?: string;
  linked_evidence_ids?: string[];
  commitment_history_rationale?: any[];
  status?: 'active' | 'deleted';
  deleted_at?: string;
  deleted_by_admin?: string;
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

    // Use flat collection structure
    const collectionPath = 'promises';
    const promiseRef = firestoreAdmin.collection(collectionPath).doc(promiseId);

    // Prepare data for Firestore, ensuring nulls are handled correctly
    // Firestore update doesn't create fields if value is undefined.
    // To explicitly set a field to null, we pass null.
    const firestoreUpdateData: { [key: string]: any } = {};
    for (const key in updateData) {
      if (Object.prototype.hasOwnProperty.call(updateData, key)) {
        // Skip read-only fields that shouldn't be updated
        if (['id', 'region_code', 'party_code', 'migration_metadata', 'ingested_at', 'explanation_enriched_at', 'linking_preprocessing_done_at'].includes(key)) {
          continue;
        }

        // If a field intended to be nullable is an empty string from form, convert to null
        if ((key === 'bc_promise_rank' || key === 'bc_promise_direction' || key === 'bc_promise_rank_rationale') && updateData[key] === '') {
          firestoreUpdateData[key] = null;
        } else if (updateData[key] === undefined) {
           // If a key exists but is undefined, we might want to remove it or set to null.
           // For `update`, undefined means no change. To remove a field, use FieldValue.delete().
           // For now, we only pass defined values or explicit nulls.
           // If you want to allow field deletion, that needs specific handling.
        } else {
          firestoreUpdateData[key] = updateData[key];
        }
      }
    }
    
    // Add a timestamp for the last update
    firestoreUpdateData.last_updated_admin = FieldValue.serverTimestamp();

    console.log(`Updating promise ${promiseId} with data:`, firestoreUpdateData);

    await promiseRef.update(firestoreUpdateData);

    return NextResponse.json({ message: 'Promise updated successfully', id: promiseId }, { status: 200 });

  } catch (error: any) {
    console.error(`Error updating promise ${promiseId}:`, error);
    let errorMessage = 'Internal server error';
    if (error.code === 'not-found') {
      errorMessage = 'Promise not found';
      return NextResponse.json({ error: errorMessage, details: error.message }, { status: 404 });
    }
    if (typeof error === 'object' && error !== null && 'message' in error) {
        errorMessage = (error as {message: string}).message;
    }
    return NextResponse.json({ error: 'Failed to update promise.', details: errorMessage }, { status: 500 });
  }
}

export async function DELETE(
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
    // Use flat collection structure
    const collectionPath = 'promises';
    const promiseRef = firestoreAdmin.collection(collectionPath).doc(promiseId);

    // Check if promise exists and is not already deleted
    const promiseDoc = await promiseRef.get();
    if (!promiseDoc.exists) {
      return NextResponse.json({ error: 'Promise not found' }, { status: 404 });
    }

    const promiseData = promiseDoc.data();
    if (promiseData?.status === 'deleted') {
      return NextResponse.json({ error: 'Promise is already deleted' }, { status: 400 });
    }

    // Soft delete by updating status and adding metadata
    const deleteUpdateData = {
      status: 'deleted',
      deleted_at: FieldValue.serverTimestamp(),
      deleted_by_admin: 'admin', // TODO: Replace with actual admin user ID when auth is implemented
      last_updated_admin: FieldValue.serverTimestamp()
    };

    console.log(`Soft deleting promise ${promiseId}`);

    await promiseRef.update(deleteUpdateData);

    return NextResponse.json({ 
      message: 'Promise soft deleted successfully', 
      id: promiseId,
      status: 'deleted'
    }, { status: 200 });

  } catch (error: any) {
    console.error(`Error deleting promise ${promiseId}:`, error);
    let errorMessage = 'Internal server error';
    if (error.code === 'not-found') {
      errorMessage = 'Promise not found';
      return NextResponse.json({ error: errorMessage, details: error.message }, { status: 404 });
    }
    if (typeof error === 'object' && error !== null && 'message' in error) {
        errorMessage = (error as {message: string}).message;
    }
    return NextResponse.json({ error: 'Failed to delete promise.', details: errorMessage }, { status: 500 });
  }
} 