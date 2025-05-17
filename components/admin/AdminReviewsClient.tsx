'use client';

import { useState } from 'react';

// Define the structure of a Potential Link document (consistent with server component)
export interface PotentialLink {
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
  created_at: string; 
  link_status: string;
}

interface AdminReviewsClientProps {
  initialPendingLinks: PotentialLink[];
  totalPendingCount: number;
  error?: string;
}

// Define sort options (can be kept here or passed as props if they become dynamic)
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

export default function AdminReviewsClient({ initialPendingLinks, totalPendingCount, error: initialError }: AdminReviewsClientProps) {
  const [pendingLinksData, setPendingLinksData] = useState<PotentialLink[]>(initialPendingLinks);
  const [isLoading, setIsLoading] = useState<{[key: string]: boolean}>({});
  const [pageError, setPageError] = useState<string | undefined>(initialError);
  const [rejectionReasons, setRejectionReasons] = useState<{[key: string]: string}>({});
  const [currentSort, setCurrentSort] = useState<string>(sortOptions[0].value);

  const getSortedLinks = (links: PotentialLink[], sortBy: string): PotentialLink[] => {
    const sorted = [...links];
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
      case 'created_at_desc':
      default:
        sorted.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
        break;
    }
    return sorted;
  };

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

  if (pageError && !displayedLinks.length && !initialError) { // Avoid showing generic error if server already sent one
    return <div style={{ color: 'red' }}>Error: {pageError}</div>;
  }
  if (initialError && !displayedLinks.length) {
    return <div style={{ color: 'red' }}>Error: {initialError}</div>;
  }

  return (
    <div style={{ padding: '20px' }}>
      {/* Title will be in the Server Component page.tsx */}
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
      {pageError && displayedLinks.length > 0 && <p style={{ color: 'red' }}>{pageError}</p>} {/* Show error even if list is present */}
      {initialError && displayedLinks.length === 0 && <p style={{ color: 'red' }}>Server Error: {initialError}</p>}
      {displayedLinks.length === 0 && !pageError && !initialError && <p>No pending reviews to display.</p>}
      
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
} 