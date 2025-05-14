import { useState } from 'react';
import type { GetServerSideProps, NextPage } from 'next';
import type { Timestamp, QueryDocumentSnapshot } from 'firebase-admin/firestore'; // For types
import { getFirestore, collection, query, where, orderBy, getDocs } from 'firebase/firestore';

// Define the structure of a Potential Link document
interface PotentialLink {
  id: string;
  promise_id: string;
  promise_text_snippet: string;
  evidence_id: string;
  evidence_title_or_summary: string;
  bill_id?: string | null;
  bill_title_snippet?: string | null;
  bill_long_title_en?: string | null;
  event_details?: string | null;
  evidence_source_url?: string | null;
  llm_explanation: string;
  llm_likelihood_score: string;
  score_keyword_overlap_jaccard: number;
  score_keyword_overlap_common_count: number;
  created_at: string; // Will be string after serialization from getServerSideProps
  link_status: string;
}

interface AdminReviewsPageProps {
  initialPendingLinks: PotentialLink[];
  totalPendingCount: number;
  error?: string;
}

export const getServerSideProps: GetServerSideProps<AdminReviewsPageProps> = async (context) => {
  // Dynamically import for server-side use only
  const { firestoreAdmin } = await import('../../lib/firebaseAdmin'); 

  // TODO: Add authentication and authorization checks here.

  try {
    // Query for the first 50 pending links for display
    const pendingLinksSnapshot = await firestoreAdmin
      .collection('promise_evidence_links')
      .where('link_status', '==', 'pending_review')
      .orderBy('created_at', 'desc')
      .limit(50)
      .get();

    // Separate query to get the total count of all pending links
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

      // Dynamically fetch bill_long_title_en if not present and bill_parl_id exists
      if (!bill_long_title_en && data.bill_parl_id) {
        try {
          const billDocSnap = await firestoreAdmin.collection('bills_data').doc(data.bill_parl_id).get();
          if (billDocSnap.exists) {
            bill_long_title_en = billDocSnap.data()?.long_title_en || null;
          }
        } catch (e) {
          console.error(`Error fetching bill_data for ${data.bill_parl_id}:`, e);
          // bill_long_title_en remains null or its initial value
        }
      }

      // Dynamically fetch evidence_source_url if not present and evidence_id exists
      if (!evidence_source_url && data.evidence_id) {
        try {
          const evidenceDocSnap = await firestoreAdmin.collection('evidence_items').doc(data.evidence_id).get();
          if (evidenceDocSnap.exists) {
            evidence_source_url = evidenceDocSnap.data()?.source_url || null;
          }
        } catch (e) {
          console.error(`Error fetching evidence_items for ${data.evidence_id}:`, e);
          // evidence_source_url remains null or its initial value
        }
      }

      return {
        id: doc.id,
        promise_id: data.promise_id || '',
        promise_text_snippet: data.promise_text_snippet || '',
        evidence_id: data.evidence_id || '', // Keep for key/internal use, even if not displayed
        evidence_title_or_summary: data.evidence_title_or_summary || '',
        bill_id: data.bill_parl_id || null, // Correctly map from bill_parl_id
        bill_title_snippet: data.bill_title_snippet || null,
        bill_long_title_en: bill_long_title_en, // Use dynamically fetched or existing value
        event_details: data.event_details || null,
        evidence_source_url: evidence_source_url, // Use dynamically fetched or existing value
        llm_explanation: data.llm_explanation || '',
        llm_likelihood_score: data.llm_likelihood_score || '',
        score_keyword_overlap_jaccard: data.keyword_overlap_score?.jaccard || 0,
        score_keyword_overlap_common_count: data.keyword_overlap_score?.common_count || 0,
        created_at: createdAtTimestamp?.toDate?.().toISOString() || new Date().toISOString(),
        link_status: data.link_status || 'pending_review',
      };
    });
    const initialPendingLinks = await Promise.all(initialPendingLinksPromises);

    return { props: { initialPendingLinks, totalPendingCount } };
  } catch (error: any) {
    console.error("Error fetching pending links:", error);
    return { props: { initialPendingLinks: [], totalPendingCount: 0, error: "Failed to load pending reviews." } };
  }
};

// Define sort options
const sortOptions = [
  { value: 'created_at_desc', label: 'Most Recent' },
  { value: 'jaccard_desc', label: 'Jaccard Score (High to Low)' },
  { value: 'jaccard_asc', label: 'Jaccard Score (Low to High)' },
  { value: 'common_keywords_desc', label: 'Common Keywords (High to Low)' },
  { value: 'common_keywords_asc', label: 'Common Keywords (Low to High)' },
  { value: 'llm_assessment_high_low', label: 'LLM Assessment (High to Low)' },
];

// Helper for LLM Assessment sorting
const assessmentOrder: { [key: string]: number } = {
  'High': 1,
  'Medium': 2,
  'Low': 3,
  'Not Related': 4,
  '': 5, // Handle empty or unexpected values
};

const AdminReviewsPage: NextPage<AdminReviewsPageProps> = ({ initialPendingLinks, totalPendingCount, error }) => {
  const [pendingLinksData, setPendingLinksData] = useState<PotentialLink[]>(initialPendingLinks);
  const [isLoading, setIsLoading] = useState<{[key: string]: boolean}>({});
  const [pageError, setPageError] = useState<string | undefined>(error);
  const [rejectionReasons, setRejectionReasons] = useState<{[key: string]: string}>({});
  const [currentSort, setCurrentSort] = useState<string>(sortOptions[0].value);

  // Function to handle sorting
  const getSortedLinks = (links: PotentialLink[], sortBy: string): PotentialLink[] => {
    const sorted = [...links]; // Create a new array to avoid mutating state directly
    switch (sortBy) {
      case 'jaccard_desc':
        sorted.sort((a, b) => b.score_keyword_overlap_jaccard - a.score_keyword_overlap_jaccard);
        break;
      case 'jaccard_asc':
        sorted.sort((a, b) => a.score_keyword_overlap_jaccard - b.score_keyword_overlap_jaccard);
        break;
      case 'common_keywords_desc':
        sorted.sort((a, b) => b.score_keyword_overlap_common_count - a.score_keyword_overlap_common_count);
        break;
      case 'common_keywords_asc':
        sorted.sort((a, b) => a.score_keyword_overlap_common_count - b.score_keyword_overlap_common_count);
        break;
      case 'llm_assessment_high_low':
        sorted.sort((a, b) => (assessmentOrder[a.llm_likelihood_score] || 5) - (assessmentOrder[b.llm_likelihood_score] || 5));
        break;
      case 'created_at_desc': // Default sort by created_at (descending)
      default:
        sorted.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
        break;
    }
    return sorted;
  };

  // Update displayed links when data or sort order changes
  // Note: initialPendingLinks is passed to useState, so this effect handles client-side sorting changes.
  const displayedLinks = getSortedLinks(pendingLinksData, currentSort);

  const handleConfirm = async (potentialLinkId: string) => {
    setIsLoading(prev => ({ ...prev, [potentialLinkId]: true }));
    try {
      const response = await fetch('/api/admin/reviews/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ potentialLinkId }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.message || 'Failed to confirm link');
      }
      setPendingLinksData(prevLinks => prevLinks.filter(link => link.id !== potentialLinkId));
      setPageError(undefined);
    } catch (err: any) {
      console.error("Confirm error:", err);
      setPageError(err.message || 'An error occurred while confirming.');
    } finally {
      setIsLoading(prev => ({ ...prev, [potentialLinkId]: false }));
    }
  };

  const handleReject = async (potentialLinkId: string) => {
    setIsLoading(prev => ({ ...prev, [potentialLinkId]: true }));
    try {
      const response = await fetch('/api/admin/reviews/reject', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ potentialLinkId, rejectionReason: rejectionReasons[potentialLinkId] || null }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.message || 'Failed to reject link');
      }
      setPendingLinksData(prevLinks => prevLinks.filter(link => link.id !== potentialLinkId));
      setPageError(undefined);
      setRejectionReasons(prev => { const newState = {...prev}; delete newState[potentialLinkId]; return newState; });
    } catch (err: any) {
      console.error("Reject error:", err);
      setPageError(err.message || 'An error occurred while rejecting.');
    } finally {
      setIsLoading(prev => ({ ...prev, [potentialLinkId]: false }));
    }
  };

  if (pageError && !displayedLinks.length) {
    return <div style={{ color: 'red' }}>Error: {pageError}</div>;
  }

  return (
    <div style={{ padding: '20px' }}>
      <h1>Admin Pending Reviews</h1>
      <p>Total items to review: {totalPendingCount}</p>
      <div style={{ marginBottom: '20px' }}>
        <label htmlFor="sort-select" style={{ marginRight: '10px' }}>Sort by:</label>
        <select 
          id="sort-select" 
          value={currentSort} 
          onChange={(e) => setCurrentSort(e.target.value)}
        >
          {sortOptions.map(option => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
      </div>
      {pageError && <p style={{ color: 'red' }}>{pageError}</p>}
      {displayedLinks.length === 0 && !pageError && <p>No pending reviews to display (or all have been processed for this page load).</p>}
      {displayedLinks.map(link => (
        <div key={link.id} style={{ border: '1px solid #ccc', padding: '15px', marginBottom: '15px', borderRadius: '5px' }}>
          <h2>Potential Link ID: {link.id}</h2>
          <p><strong>Status:</strong> {link.link_status}</p>
          <p><strong>Promise ID:</strong> {link.promise_id}</p>
          <p><em>Promise Snippet:</em> {link.promise_text_snippet}</p>
          <p><em>Evidence Title/Summary:</em> {link.evidence_title_or_summary}</p>
          {link.evidence_source_url && <p><strong>Evidence Source:</strong> <a href={link.evidence_source_url} target="_blank" rel="noopener noreferrer">{link.evidence_source_url}</a></p>}
          {link.bill_id && <p><strong>Bill Parl ID:</strong> {link.bill_id}</p>}
          {link.bill_title_snippet && <p><em>Bill Short Title:</em> {link.bill_title_snippet}</p>}
          {link.bill_long_title_en && <p><em>Bill Long Title:</em> {link.bill_long_title_en}</p>}
          {link.event_details && <p><strong>Event:</strong> {link.event_details}</p>}
          <p><strong>LLM Assessment:</strong> {link.llm_likelihood_score}</p>
          <p><strong>LLM Explanation:</strong> {link.llm_explanation}</p>
          <p><strong>Jaccard Score:</strong> {link.score_keyword_overlap_jaccard?.toFixed(3)}</p>
          <p><strong>Common Keywords:</strong> {link.score_keyword_overlap_common_count}</p>
          <p><strong>Created At:</strong> {new Date(link.created_at).toLocaleString()}</p>
          
          <div style={{ marginTop: '10px' }}>
            <textarea 
              placeholder="Rejection reason (optional)"
              value={rejectionReasons[link.id] || ''}
              onChange={(e) => setRejectionReasons(prev => ({ ...prev, [link.id]: e.target.value }))}
              style={{ width: 'calc(100% - 20px)', minHeight: '50px', marginBottom: '10px' }}
              disabled={isLoading[link.id]}
            />
            <button 
              onClick={() => handleConfirm(link.id)} 
              disabled={isLoading[link.id] || (!!rejectionReasons[link.id] && rejectionReasons[link.id].trim() !== '' )}
              style={{ marginRight: '10px', padding: '8px 12px' }}
            >
              {isLoading[link.id] ? 'Processing...' : 'Confirm Link'}
            </button>
            <button 
              onClick={() => handleReject(link.id)} 
              disabled={isLoading[link.id]}
              style={{ padding: '8px 12px', backgroundColor: '#f44336', color: 'white' }}
            >
              {isLoading[link.id] ? 'Processing...' : 'Reject Link'}
            </button>
          </div>
        </div>
      ))}
    </div>
  );
};

export default AdminReviewsPage; 