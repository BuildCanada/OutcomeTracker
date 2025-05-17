import type { NextApiRequest, NextApiResponse } from 'next';
import { firestoreAdmin, firebaseAdmin } from '../../../../lib/firebaseAdmin'; // Adjust path as needed
// Make sure to use firebaseAdmin.firestore.Transaction for the type if not importing Transaction directly
import * as admin from 'firebase-admin';

interface ConfirmRequestData {
  potentialLinkId: string;
}

interface ApiResponseData {
  status: string;
  message: string;
  error?: string;
}

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<ApiResponseData>
) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', ['POST']);
    return res.status(405).json({ status: "error", message: `Method ${req.method} Not Allowed` });
  }

  // TODO: Add authentication and authorization checks here
  // For example, check if the user is authenticated and has admin privileges.
  // if (!context.auth || !context.auth.token.isAdmin) { // Example with NextAuth.js or similar
  //   return res.status(401).json({ status: "error", message: "Unauthenticated or unauthorized" });
  // }

  const { potentialLinkId } = req.body as ConfirmRequestData;

  if (!potentialLinkId) {
    return res.status(400).json({ status: "error", message: "potentialLinkId is required." });
  }

  const db = admin.firestore();
  const promisesCollectionName = "promises";
  const potentialLinksCollectionName = "promise_evidence_links";
  const evidenceItemsCollectionName = "evidence_items"; // Assuming this is prod or also needs review
  const potentialLinkRef = db.collection(potentialLinksCollectionName).doc(potentialLinkId);

  try {
    const result = await db.runTransaction(async (transaction: admin.firestore.Transaction) => {
      const potentialLinkDoc = await transaction.get(potentialLinkRef);

      if (!potentialLinkDoc.exists) {
        // Use a specific error code or message for not found
        throw new Error(`Potential link ${potentialLinkId} not found.`); 
      }

      const linkData = potentialLinkDoc.data();
      if (!linkData) {
         throw new Error(`Data missing for potential link ${potentialLinkId}.`);
      }

      if (linkData.link_status !== "pending_review") {
        // This isn't strictly an error for the transaction, but a state check.
        // Consider how to signal this: maybe a specific success message or a different status code.
        return { 
          status: "noop", 
          message: `Link ${potentialLinkId} is already processed with status: ${linkData.link_status}. No action taken.` 
        };
      }

      const promiseId = linkData.promise_id;
      const evidenceId = linkData.evidence_id;

      if (!promiseId || !evidenceId) {
        console.error(
          "Link data is missing promise_id or evidence_id for link:",
          potentialLinkId,
          linkData
        );
        // This indicates a data integrity issue.
        throw new Error("Potential link is missing promise_id or evidence_id."); 
      }

      const promiseRef = db.collection(promisesCollectionName).doc(promiseId);
      const evidenceRef = db.collection(evidenceItemsCollectionName).doc(evidenceId);

      transaction.update(potentialLinkRef, {
        link_status: "confirmed",
        reviewed_at: admin.firestore.FieldValue.serverTimestamp(),
        // reviewer_id: context.auth.uid, // If you re-introduce reviewer_id from auth context
      });

      transaction.update(promiseRef, {
        linked_evidence_ids: admin.firestore.FieldValue.arrayUnion(evidenceId),
      });

      transaction.update(evidenceRef, {
        promise_ids: admin.firestore.FieldValue.arrayUnion(promiseId),
      });

      return { 
        status: "success", 
        message: `Link ${potentialLinkId} confirmed successfully.` 
      };
    });

    if (result.status === "noop") {
        return res.status(200).json(result);
    }
    return res.status(200).json(result);

  } catch (error: any) {
    console.error(`Error confirming link ${potentialLinkId}:`, error);
    if (error.message.includes("not found")) {
        return res.status(404).json({ status: "error", message: error.message });
    }
    return res.status(500).json({ 
      status: "error", 
      message: `Failed to confirm link ${potentialLinkId}.`, 
      error: error.message 
    });
  }
} 