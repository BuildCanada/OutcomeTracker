import type { Timestamp, QueryDocumentSnapshot } from 'firebase-admin/firestore'; // For types
import { firestoreAdmin } from '@/lib/firebaseAdmin'; 
import AdminReviewsClient, { PotentialLink } from '@/components/admin/AdminReviewsClient';
import React from 'react';

// This function fetches the data on the server.
async function getPendingLinksData() {
  // TODO: Add authentication and authorization checks here.
  // Similar to what was in getServerSideProps: context.req, context.res can be accessed 
  // via headers() and cookies() from 'next/headers' if needed for auth.

  try {
    const pendingLinksSnapshot = await firestoreAdmin
      .collection('promise_evidence_links')
      .where('link_status', '==', 'pending_review')
      .orderBy('created_at', 'desc')
      .limit(50) // Keep pagination in mind for real applications
      .get();

    const countSnapshot = await firestoreAdmin
      .collection('promise_evidence_links')
      .where('link_status', '==', 'pending_review')
      .count()
      .get();
    const totalPendingCount = countSnapshot.data().count;

    const initialPendingLinksPromises = pendingLinksSnapshot.docs.map(async (doc: QueryDocumentSnapshot) => {
      const data = doc.data();
      const createdAtTimestamp = data.created_at as Timestamp;

      let bill_long_title_en = data.bill_long_title_en;
      let evidence_source_url = data.evidence_source_url;

      if (!bill_long_title_en && data.bill_parl_id) {
        try {
          const billDocSnap = await firestoreAdmin.collection('bills_data').doc(data.bill_parl_id).get();
          if (billDocSnap.exists) {
            bill_long_title_en = billDocSnap.data()?.long_title_en || null;
          }
        } catch (e) {
          console.error(`Error fetching bill_data for ${data.bill_parl_id}:`, e);
        }
      }

      if (!evidence_source_url && data.evidence_id) {
        try {
          const evidenceDocSnap = await firestoreAdmin.collection('evidence_items').doc(data.evidence_id).get();
          if (evidenceDocSnap.exists) {
            evidence_source_url = evidenceDocSnap.data()?.source_url || null;
          }
        } catch (e) {
          console.error(`Error fetching evidence_items for ${data.evidence_id}:`, e);
        }
      }

      return {
        id: doc.id,
        promise_id: data.promise_id || '',
        promise_text_snippet: data.promise_text_snippet || '',
        evidence_id: data.evidence_id || '',
        evidence_title_or_summary: data.evidence_title_or_summary || '',
        bill_id: data.bill_parl_id || null,
        bill_title_snippet: data.bill_title_snippet || null,
        bill_long_title_en: bill_long_title_en,
        event_details: data.event_details || null,
        evidence_source_url: evidence_source_url,
        llm_explanation: data.llm_explanation || '',
        llm_likelihood_score: data.llm_likelihood_score || '',
        score_keyword_overlap_jaccard: data.keyword_overlap_score?.jaccard || 0,
        score_keyword_overlap_common_count: data.keyword_overlap_score?.common_count || 0,
        created_at: createdAtTimestamp?.toDate?.().toISOString() || new Date().toISOString(),
        link_status: data.link_status || 'pending_review',
      } as PotentialLink;
    });

    const initialPendingLinks = await Promise.all(initialPendingLinksPromises);
    return { initialPendingLinks, totalPendingCount, error: null };

  } catch (error: any) {
    console.error("Error fetching pending links for AdminReviewsPage:", error);
    // In Server Components, you can throw an error to trigger error.tsx, or return a prop
    return { initialPendingLinks: [], totalPendingCount: 0, error: "Failed to load pending reviews from server." };
  }
}

export default async function AdminReviewsPage() {
  const { initialPendingLinks, totalPendingCount, error } = await getPendingLinksData();

  return (
    <>
      {/* <h1 className="text-2xl font-semibold mb-6 pl-5 pt-5">Admin Pending Reviews</h1> */}
      {/* Heading removed, handled by layout/tabs */}
      <AdminReviewsClient 
        initialPendingLinks={initialPendingLinks} 
        totalPendingCount={totalPendingCount}
        error={error || undefined} 
      />
    </>
  );
} 