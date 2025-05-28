import { NextRequest, NextResponse } from 'next/server';
import { firestoreAdmin } from '@/lib/firebaseAdmin';

export async function PUT(request: NextRequest) {
  // TODO: Implement robust authentication and authorization here
  // For example, check if the user is an admin
  // if (!isAdmin(request)) { 
  //   return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  // }

  try {
    const body = await request.json();
    const { current_selected_parliament_session } = body;

    if (!current_selected_parliament_session) {
      return NextResponse.json({ error: 'current_selected_parliament_session is required' }, { status: 400 });
    }

    // Validate that the parliament session exists
    const sessionDoc = await firestoreAdmin.collection('parliament_session').doc(current_selected_parliament_session).get();
    if (!sessionDoc.exists) {
      return NextResponse.json({ error: 'Parliament session not found' }, { status: 404 });
    }

    // Update the global config document
    const globalConfigRef = firestoreAdmin.doc('admin_settings/global_config');
    await globalConfigRef.set({
      current_selected_parliament_session,
      last_updated: new Date().toISOString()
    }, { merge: true });

    return NextResponse.json({ 
      message: 'Admin settings updated successfully', 
      current_selected_parliament_session 
    }, { status: 200 });

  } catch (error: any) {
    console.error('Error updating admin settings:', error);
    let errorMessage = 'Internal server error';
    if (typeof error === 'object' && error !== null && 'message' in error) {
      errorMessage = (error as {message: string}).message;
    }
    return NextResponse.json({ error: 'Failed to update admin settings.', details: errorMessage }, { status: 500 });
  }
}

export async function GET() {
  try {
    const globalConfigDoc = await firestoreAdmin.doc('admin_settings/global_config').get();
    
    if (!globalConfigDoc.exists) {
      return NextResponse.json({ error: 'Global config not found' }, { status: 404 });
    }

    const data = globalConfigDoc.data();
    return NextResponse.json(data, { status: 200 });

  } catch (error: any) {
    console.error('Error fetching admin settings:', error);
    let errorMessage = 'Internal server error';
    if (typeof error === 'object' && error !== null && 'message' in error) {
      errorMessage = (error as {message: string}).message;
    }
    return NextResponse.json({ error: 'Failed to fetch admin settings.', details: errorMessage }, { status: 500 });
  }
} 