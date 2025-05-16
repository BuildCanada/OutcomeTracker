import React, { useState, useEffect } from 'react';
import { PromiseData, EvidenceItem } from '../lib/types';
import { Timestamp } from 'firebase/firestore';
import TimelineNode from './TimelineNode'; // Import the new component
// import EvidenceDetailsDisplay from './EvidenceDetailsDisplay'; // Keep for later if needed

interface PromiseProgressTimelineProps {
  promise: PromiseData;
}

// Type for items to be displayed on the timeline, unifying mandate and evidence
export interface TimelineDisplayEvent {
  id: string; // Can be promise.id for mandate, or evidence.id for evidence
  type: 'mandate' | 'evidence';
  date: Timestamp | string; // Mandate date_issued is string, evidence_date is Timestamp
  title: string; // Mandate text (or a snippet), or evidence.title_or_summary
  fullText: string; // Full mandate text or evidence.description_or_details
  sourceUrl?: string; // Only for evidence items
}

const formatDate = (dateInput: Timestamp | string): string => {
  if (!dateInput) return 'Date not available';
  let dateObj: Date;
  if (dateInput instanceof Timestamp) {
    dateObj = dateInput.toDate();
  } else if (typeof dateInput === 'string') {
    dateObj = new Date(dateInput);
    if (isNaN(dateObj.getTime())) { // Check if date string was valid
        // Attempt to parse YYYY-MM-DD if common ISO format was used without time
        const parts = dateInput.split('-');
        if (parts.length === 3) {
            dateObj = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
        }
        if (isNaN(dateObj.getTime())) return 'Invalid date string';
    }
  } else {
    return 'Invalid date format';
  }
  return dateObj.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
};

const PromiseProgressTimeline: React.FC<PromiseProgressTimelineProps> = ({ promise }) => {
  const [timelineEvents, setTimelineEvents] = useState<TimelineDisplayEvent[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<TimelineDisplayEvent | null>(null);

  useEffect(() => {
    if (!promise) return;

    const events: TimelineDisplayEvent[] = [];

    // 1. Add the mandate commitment as the first event
    if (promise.source_type === 'Mandate Letter Commitment (Structured)' && promise.date_issued) {
      events.push({
        id: `mandate-${promise.id}`,
        type: 'mandate',
        date: promise.date_issued,
        title: promise.text.substring(0, 70) + (promise.text.length > 70 ? '...' : ''), // Shorter snippet for node
        fullText: promise.text,
        // No sourceUrl for mandate letter directly from here, could link to a general mandate letter page if exists
      });
    }

    // 2. Add evidence items
    // This component will use promise.evidence directly, which should be populated by the data fetching logic
    if (promise.evidence) {
      const evidenceEvents: TimelineDisplayEvent[] = promise.evidence.map((item: EvidenceItem, index: number) => {
        const evidenceId = item.id ? item.id : `generated-evidence-${index}`;
        if (!item.id) {
          console.warn(`Evidence item at index ${index} for promise ${promise.id} has a missing ID. Using generated ID for key: ${evidenceId}`);
        }
        return {
          id: `evidence-${evidenceId}`, // Use the potentially generated ID
          type: 'evidence',
          date: item.evidence_date,
          title: item.title_or_summary.substring(0, 70) + (item.title_or_summary.length > 70 ? '...' : ''),
          fullText: item.description_or_details || 'No further details provided.',
          sourceUrl: item.source_url,
        };
      });
      events.push(...evidenceEvents);
    }

    // Sort events by date (ascending for timeline)
    events.sort((a, b) => {
      const dateA = a.date instanceof Timestamp ? a.date.toMillis() : new Date(a.date as string).getTime();
      const dateB = b.date instanceof Timestamp ? b.date.toMillis() : new Date(b.date as string).getTime();
      if (isNaN(dateA) && isNaN(dateB)) return 0;
      if (isNaN(dateA)) return 1; // Put potentially invalid dates later
      if (isNaN(dateB)) return -1;
      return dateA - dateB;
    });

    setTimelineEvents(events);
    if (events.length > 0) {
      setSelectedEvent(events[0]);
    } else {
      setSelectedEvent(null);
    }

  }, [promise]);

  const handleEventSelect = (event: TimelineDisplayEvent) => {
    setSelectedEvent(event);
  };

  if (!promise) {
    return <p>No promise data available.</p>;
  }
  
  if (timelineEvents.length === 0 && !(promise.source_type === 'Mandate Letter Commitment (Structured)' && promise.date_issued)) {
    return <p className="text-sm text-gray-500 italic p-4">No timeline events to display for this promise.</p>;
  }

  return (
    <div className="my-6 font-sans">
      <h3 className="text-lg font-semibold text-gray-700 mb-5 px-3">Timeline of progress</h3>
      
      {/* Horizontal Timeline Section - visible on md screens and up */}
      <div className="hidden md:block mt-6 px-4 py-4 border border-gray-100 rounded-md bg-gray-50 relative overflow-hidden">
        <div className="overflow-x-auto pb-2" style={{ maxWidth: "100%", overflowY: "hidden" }}>
          <ul className="timeline md:timeline-horizontal">
            {timelineEvents.map((event, index) => {
              const isFirstEvent = index === 0;
              const isLastEvent = index === timelineEvents.length - 1;
              
              let liClass = "";
              if (isFirstEvent) {
                liClass = "first-occurrence";
              } else if (isLastEvent) {
                liClass = "last-occurrence";
              }
              
              const positionClass = index % 2 === 0 ? "md:timeline-start" : "md:timeline-end";

              return (
                <li key={event.id} className={`${liClass}`}>
                  {!isFirstEvent && <hr className="bg-red-600 opacity-75" />}
                  <div className="timeline-middle">
                    <div className={`w-4 h-4 rounded-full ${isFirstEvent || isLastEvent ? 'bg-red-600' : 'bg-gray-500'}`}></div>
                  </div>
                  <div className={`${positionClass} timeline-box-wrapper`}>
                    <TimelineNode 
                      event={event} 
                      isSelected={selectedEvent?.id === event.id}
                      onClick={() => handleEventSelect(event)}
                      isFirst={isFirstEvent}
                      isLast={isLastEvent}
                    />
                  </div>
                  {!isLastEvent && <hr className="bg-red-600 opacity-75" />} 
                </li>
              );
            })}
          </ul>
        </div>
      </div>

      {/* Vertical Timeline Section - visible on screens smaller than md */}
      <div className="block md:hidden px-2 mb-6">
        {timelineEvents.map((event, index) => (
            <div key={event.id} className="flex mb-4">
                <div className="flex flex-col items-center mr-4">
                    <div 
                        onClick={() => handleEventSelect(event)}
                        className={`cursor-pointer w-3 h-3 rounded-full border-2 border-white shrink-0 
                                    ${event.type === 'mandate' && index === 0 ? 'bg-red-500' : (index === timelineEvents.length -1 && event.type === 'evidence' ? 'bg-red-500' : 'bg-gray-500')} 
                                    ${selectedEvent?.id === event.id ? 'ring-2 ' + (event.type === 'mandate' && index === 0 ? 'ring-red-300' : (index === timelineEvents.length -1 && event.type === 'evidence' ? 'ring-red-300' : 'ring-blue-300')) : ''}
                                  `}
                    ></div>
                    {index < timelineEvents.length - 1 && (
                        <div className="w-0.5 flex-grow bg-gray-300"></div>
                    )}
                </div>
                <div className="flex-grow">
                    <TimelineNode 
                        event={event} 
                        isSelected={selectedEvent?.id === event.id}
                        onClick={() => handleEventSelect(event)}
                        isFirst={index === 0}
                        isLast={index === timelineEvents.length - 1 && event.type ==='evidence' }
                    />
                </div>
            </div>
        ))}
      </div>

      {/* Selected Event Details Section - common for both layouts */}
      {selectedEvent && (
        <div className="p-4 bg-gray-50 rounded-md border border-gray-200 mx-1 md:mx-3 mt-4">
          <h4 className="font-semibold text-gray-700 mb-2 text-md">{selectedEvent.type === 'mandate' ? 'Mandate Commitment Details' : 'Evidence Details'}</h4>
          <p className="text-xs text-gray-500 mb-1">Date: {formatDate(selectedEvent.date)}</p>
          <p className="font-medium text-gray-800 mb-2 text-sm">{selectedEvent.title}</p>
          <p className="text-gray-600 text-sm whitespace-pre-wrap mb-3">{selectedEvent.fullText}</p>
          {selectedEvent.sourceUrl && (
            <a 
              href={selectedEvent.sourceUrl} 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-blue-600 hover:text-blue-800 hover:underline text-sm font-medium"
            >
              View Source
            </a>
          )}
        </div>
      )}
      {!selectedEvent && timelineEvents.length > 0 && (
         <p className="text-center text-gray-500 italic py-3">Select an event from the timeline to see details.</p>
      )}
    </div>
  );
};

export default PromiseProgressTimeline; 