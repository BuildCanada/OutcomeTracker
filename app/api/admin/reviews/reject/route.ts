import { NextResponse } from 'next/server';
import { firestoreAdmin } from '@/lib/firebaseAdmin';
import { FieldValue } from 'firebase-admin/firestore';

// TODO: Implement proper authentication and authorization for this route

export async function POST(request: Request) {
  let potentialLinkId: string | undefined = undefined; // Define here for broader scope
  try {
    const body = await request.json();
    potentialLinkId = body.potentialLinkId; // Assign value from body
    const { rejectionReason } = body;

    if (!potentialLinkId) {
      return NextResponse.json({ status: "error", message: 'Potential Link ID is required' }, { status: 400 });
    }

    const linkRef = firestoreAdmin.collection('promise_evidence_links').doc(potentialLinkId as string);
    const potentialLinkDoc = await linkRef.get();

    if (!potentialLinkDoc.exists) {
      return NextResponse.json({ status: "error", message: `Potential link ${potentialLinkId} not found.` }, { status: 404 });
    }

    const linkData = potentialLinkDoc.data();
    if (!linkData) {
        // This case might be redundant if !potentialLinkDoc.exists is caught first, but good for safety.
        return NextResponse.json({ status: "error", message: `Data missing for potential link ${potentialLinkId}.` }, { status: 404 });
    }

    if (linkData.link_status !== "pending_review") {
      return NextResponse.json({
        status: "noop",
        message: `Link ${potentialLinkId} is already processed with status: ${linkData.link_status}. No action taken.`,
      }, { status: 200 }); // Use 200 for NOOP as per old API
    }

    await linkRef.update({
      link_status: "rejected",
      reviewed_at: FieldValue.serverTimestamp(),
      reviewer_notes: rejectionReason || null, // Changed from rejection_reason to reviewer_notes
      // reviewer_id: /* context.auth.uid */ null, // Add if auth is implemented
    });

    return NextResponse.json({ 
      status: "success", 
      message: `Link ${potentialLinkId} rejected.` 
    }, { status: 200 });

  } catch (error: any) {
    console.error(`Error rejecting link ${potentialLinkId || 'unknown'}:`, error); // Use potentialLinkId here
    return NextResponse.json({ 
      status: "error", 
      message: `Failed to reject link ${potentialLinkId || 'unknown'}.`, // Use potentialLinkId here
      error: error.message 
    }, { status: 500 });
  }
} 