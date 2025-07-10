import React from 'react';
import { Timestamp } from 'firebase/firestore';
import type { TimelineDisplayEvent } from './PromiseProgressTimeline'; // Assuming type is exported

interface TimelineNodeProps {
  event: TimelineDisplayEvent;
  isSelected: boolean;
  onClick: () => void;
  isFirst: boolean; // To identify the "First mention" mandate event
  isLast: boolean;  // To potentially style the last event as "Most Recent"
}

const formatDateForNode = (dateInput: Timestamp | string | { seconds: number; nanoseconds: number }): string => {
  if (!dateInput) return 'Date N/A';
  let dateObj: Date;
  
  if (dateInput instanceof Timestamp) {
    dateObj = dateInput.toDate();
  } else if (typeof dateInput === 'object' && dateInput !== null && 
             typeof dateInput.seconds === 'number' && 
             typeof dateInput.nanoseconds === 'number') {
    // Handle serialized Timestamp objects from API
    dateObj = new Date(dateInput.seconds * 1000);
  } else if (typeof dateInput === 'string') {
    dateObj = new Date(dateInput);
    if (isNaN(dateObj.getTime())) {
        const parts = dateInput.split('-');
        if (parts.length === 3) {
            dateObj = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
        }
        if (isNaN(dateObj.getTime())) return 'Invalid Date';
    }
  } else {
    console.warn('[TimelineNode] Unknown date format:', dateInput);
    return 'Unknown Date';
  }
  
  if (isNaN(dateObj.getTime())) {
    console.warn('[TimelineNode] Invalid date created from:', dateInput);
    return 'Invalid Date';
  }
  
  // Format from user HTML: April 4, 2025
  return dateObj.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
};

// Function to map raw evidence source types to shorter, more readable forms
const formatEvidenceSourceType = (rawSourceType: string): string => {
  const mappings: Record<string, string> = {
    'OrderInCouncil (PCO)': 'ORDER IN COUNCIL',
    'ORDERINCOUNCIL (PCO)': 'ORDER IN COUNCIL',
    'Bill Event (LEGISinfo)': 'BILL',
    'REGULATION (CANADA GAZETTE P2)': 'CANADA GAZETTE',
    'Regulation (Canada Gazette P2)': 'CANADA GAZETTE',
    'NEWS RELEASE (CANADA.CA)': 'NEWS RELEASE',
    'News Release (Canada.ca)': 'NEWS RELEASE'
  };
  
  return mappings[rawSourceType] || rawSourceType.toUpperCase();
};

const TimelineNode: React.FC<TimelineNodeProps> = ({ event, isSelected, onClick, isFirst, isLast }) => {
  const isFirstMention = isFirst;

  let boxClasses = "w-full md:w-auto max-w-[150px] md:max-w-[200px] cursor-pointer hover:shadow-md transition-shadow p-3 border border-gray-200 text-gray-900";
  const titleClasses = "font-medium line-clamp-2 text-sm";
  const dateClasses = "text-xs mt-2 text-gray-500 font-mono";
  const pillClasses = "inline-flex items-center border px-2.5 py-0.5 transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 mb-2 text-xs border-gray-200";

  // Retaining isSelected styling for accessibility / alternative interaction model
  if (isSelected) {
    boxClasses += " ring-2 ring-offset-2 ring-blue-500 bg-blue-50";
  } else {
    boxClasses += " bg-white";
  }

  // For evidence items, show a brief description from the title_or_summary
  // For mandate items, show the truncated text
  const displayDescription = event.type === 'evidence' 
    ? event.title // This is already truncated to 60 chars in the timeline setup
    : event.title; // For mandate, this is also the truncated text

  // Get the evidence source type for display
  const evidenceTypeDisplay = event.type === 'evidence' && event.evidenceSourceType 
    ? formatEvidenceSourceType(event.evidenceSourceType)
    : 'EVIDENCE';

  return (
    <div className={boxClasses} onClick={onClick}>
      {isFirstMention && (
        <div className={`${pillClasses} bg-green-50 text-green-700 border-green-200`}>
          First mention
        </div>
      )}
      {isLast && event.type === 'evidence' && !isFirstMention && (
        <div className={`${pillClasses} bg-blue-50 text-blue-700 border-blue-200`}>
          Most recent
        </div>
      )}
      
      {/* Evidence type indicator */}
      {event.type === 'evidence' && (
        <div className="text-xs text-gray-500 mb-1 uppercase tracking-wide">
          {evidenceTypeDisplay}
        </div>
      )}
      {event.type === 'mandate' && (
        <div className="text-xs text-gray-500 mb-1 uppercase tracking-wide">
          Mandate
        </div>
      )}
      
      {/* Main content */}
      <div className={titleClasses}>{displayDescription}</div>
      
      {/* Date */}
      <div className={dateClasses}>{formatDateForNode(event.date)}</div>
    </div>
  );
};

export default TimelineNode; 