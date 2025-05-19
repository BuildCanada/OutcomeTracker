import { NextResponse } from 'next/server';
import { firestoreAdmin } from '@/lib/firebaseAdmin';
import { FieldValue, Transaction } from 'firebase-admin/firestore';

// TODO: Implement proper authentication and authorization for this route
// For example, check if the user is an admin.

export async function POST(request: Request) {
  const { potentialLinkId } = await request.json();

  if (!potentialLinkId) {
    return NextResponse.json({ status: "error", message: 'Potential Link ID is required' }, { status: 400 });
  }

  const linkRef = firestoreAdmin.collection('promise_evidence_links').doc(potentialLinkId as string);
  // const promisesCollectionName = "promises"; // No longer needed if promise_id is a full path
  const evidenceItemsCollectionName = "evidence_items";

  try {
    const result = await firestoreAdmin.runTransaction(async (transaction: Transaction) => {
      const potentialLinkDoc = await transaction.get(linkRef);

      if (!potentialLinkDoc.exists) {
        // This error will be caught by the outer catch and can return a 404
        throw new Error(`Potential link ${potentialLinkId} not found.`);
      }

      const linkData = potentialLinkDoc.data();
      if (!linkData) {
        throw new Error(`Data missing for potential link ${potentialLinkId}.`);
      }

      if (linkData.link_status !== "pending_review") {
        return { 
          status: "noop", 
          message: `Link ${potentialLinkId} is already processed with status: ${linkData.link_status}. No action taken.` 
        };
      }

      const promiseId = linkData.promise_id;
      const evidenceId = linkData.evidence_id;

      if (!promiseId || !evidenceId) {
        console.error("Link data is missing promise_id or evidence_id for link:", potentialLinkId, linkData);
        throw new Error("Potential link is missing promise_id or evidence_id.");
      }

      // Assuming linkData.promise_id now stores the FULL PATH to the promise document
      const promiseRef = firestoreAdmin.doc(promiseId as string);
      const evidenceRef = firestoreAdmin.collection(evidenceItemsCollectionName).doc(evidenceId as string); // Ensure evidenceId is also treated as string for doc path

      transaction.update(linkRef, {
        link_status: "confirmed",
        reviewed_at: FieldValue.serverTimestamp(),
        // reviewer_id: /* context.auth.uid */ null, // Add if auth is implemented
      });

      transaction.update(promiseRef, {
        linked_evidence_ids: FieldValue.arrayUnion(evidenceId),
      });

      transaction.update(evidenceRef, {
        promise_ids: FieldValue.arrayUnion(promiseId),
      });

      return { 
        status: "success", 
        message: `Link ${potentialLinkId} confirmed successfully.` 
      };
    });

    // Handle NOOP case from transaction
    if (result.status === "noop") {
        return NextResponse.json(result, { status: 200 }); // Or a different status like 202 Accepted
    }
    // Handle SUCCESS case from transaction
    return NextResponse.json(result, { status: 200 });

  } catch (error: any) {
    console.error(`Error confirming link ${potentialLinkId}:`, error);
    if (error.message.includes("not found")) {
        return NextResponse.json({ status: "error", message: error.message }, { status: 404 });
    }
    return NextResponse.json({ 
      status: "error", 
      message: `Failed to confirm link ${potentialLinkId}.`, 
      error: error.message 
    }, { status: 500 });
  }
} 