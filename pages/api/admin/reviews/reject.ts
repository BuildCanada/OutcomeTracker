import type { NextApiRequest, NextApiResponse } from 'next';
import { firestoreAdmin, firebaseAdmin } from '../../../../lib/firebaseAdmin'; // Adjust path as needed

interface RejectRequestData {
  potentialLinkId: string;
  rejectionReason?: string | null;
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

  const { potentialLinkId, rejectionReason } = req.body as RejectRequestData;

  if (!potentialLinkId) {
    return res.status(400).json({ status: "error", message: "potentialLinkId is required." });
  }

  const potentialLinkRef = firestoreAdmin.collection("promise_evidence_links").doc(potentialLinkId);

  try {
    const potentialLinkDoc = await potentialLinkRef.get();
    if (!potentialLinkDoc.exists) {
      return res.status(404).json({ status: "error", message: `Potential link ${potentialLinkId} not found.` });
    }

    const linkData = potentialLinkDoc.data();
    if (!linkData) {
        return res.status(404).json({ status: "error", message: `Data missing for potential link ${potentialLinkId}.` });
    }

    if (linkData.link_status !== "pending_review") {
      return res.status(200).json({
        status: "noop",
        message: `Link ${potentialLinkId} is already processed with status: ${linkData.link_status}. No action taken.`,
      });
    }

    await potentialLinkRef.update({
      link_status: "rejected",
      reviewed_at: firebaseAdmin.firestore.FieldValue.serverTimestamp(),
      reviewer_notes: rejectionReason || null,
      // reviewer_id: context.auth.uid, // If you re-introduce reviewer_id from auth context
    });

    return res.status(200).json({ 
      status: "success", 
      message: `Link ${potentialLinkId} rejected.` 
    });

  } catch (error: any) {
    console.error(`Error rejecting link ${potentialLinkId}:`, error);
    return res.status(500).json({ 
      status: "error", 
      message: `Failed to reject link ${potentialLinkId}.`, 
      error: error.message 
    });
  }
} 