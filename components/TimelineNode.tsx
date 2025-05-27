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

const formatDateForNode = (dateInput: Timestamp | string): string => {
  if (!dateInput) return 'Date N/A';
  let dateObj: Date;
  if (dateInput instanceof Timestamp) {
    dateObj = dateInput.toDate();
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
    return 'Unknown Date';
  }
  // Format from user HTML: April 4, 2025
  return dateObj.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
};

const TimelineNode: React.FC<TimelineNodeProps> = ({ event, isSelected, onClick, isFirst, isLast }) => {
  const isMandate = event.type === 'mandate';
  const isFirstMention = isFirst;
  const isMostRecentEvidence = isLast && event.type === 'evidence' && !isFirstMention;

  let boxClasses = "w-full md:w-auto max-w-[300px] md:max-w-none cursor-pointer hover:shadow-md transition-shadow p-3 rounded-md bg-white border border-gray-200";
  let titleClasses = "font-medium line-clamp-3 text-gray-900";
  let dateClasses = "text-xs mt-1 text-gray-700";
  let pillClasses = "inline-flex items-center rounded-full border px-2.5 py-0.5 font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 mb-2 text-xs text-gray-900 border-gray-900";

  // Retaining isSelected styling for accessibility / alternative interaction model
  if (isSelected) {
     boxClasses +=  " ring-2 ring-offset-2 ring-red-500";
  }

  return (
    // The parent <li> will handle timeline-start/end. This component is the content box.
    <div className={boxClasses} onClick={onClick}>
      {isFirstMention && (
        <div className={pillClasses}>
          First mention
        </div>
      )}
      {isLast && event.type === 'evidence' && !isFirstMention && ( // Show "Most recent" only on the last *evidence* item, if it's not also the first mandate
        <div className={pillClasses}>
          Most recent
        </div>
      )}
      <div className={titleClasses}>{event.title}</div>
      <div className={dateClasses}>{formatDateForNode(event.date)}</div>
    </div>
  );
};

export default TimelineNode; 