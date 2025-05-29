"use client";

import React, { useState, useEffect, useRef } from 'react';
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
  title: string; // Truncated for timeline node
  fullTitle: string; // Full mandate text or evidence.title_or_summary
  fullText: string; // Full mandate text or evidence.description_or_details
  sourceUrl?: string; // Only for evidence items
  evidenceSourceType?: string; // Optional evidence source type
}

const formatDate = (dateInput: Timestamp | string | any): string => {
  if (!dateInput) return 'Date not available';
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
    if (isNaN(dateObj.getTime())) { // Check if date string was valid
        // Attempt to parse YYYY-MM-DD if common ISO format was used without time
        const parts = dateInput.split('-');
        if (parts.length === 3) {
            dateObj = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
        }
        if (isNaN(dateObj.getTime())) return 'Invalid date string';
    }
  } else {
    console.warn('[PromiseProgressTimeline] Unknown date format:', dateInput);
    return 'Invalid date format';
  }
  
  if (isNaN(dateObj.getTime())) {
    console.warn('[PromiseProgressTimeline] Invalid date created from:', dateInput);
    return 'Invalid date';
  }
  
  return dateObj.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
};

const PromiseProgressTimeline: React.FC<PromiseProgressTimelineProps> = ({ promise }) => {
  const [timelineEvents, setTimelineEvents] = useState<TimelineDisplayEvent[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<TimelineDisplayEvent | null>(null);
  const timelineRef = useRef<HTMLDivElement>(null);

  // Add effect to scroll to selected event
  useEffect(() => {
    if (selectedEvent && timelineRef.current) {
      const timelineContainer = timelineRef.current;
      const selectedElement = timelineContainer.querySelector(`[data-event-id="${selectedEvent.id}"]`);
      
      if (selectedElement) {
        const containerWidth = timelineContainer.offsetWidth;
        const elementLeft = (selectedElement as HTMLElement).offsetLeft;
        const elementWidth = (selectedElement as HTMLElement).offsetWidth;
        
        // Calculate scroll position to center the element
        const scrollLeft = elementLeft - (containerWidth / 2) + (elementWidth / 2);
        
        timelineContainer.scrollTo({
          left: scrollLeft,
          behavior: 'smooth'
        });
      }
    }
  }, [selectedEvent]);

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
        fullTitle: promise.text,
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
        
        // Create a brief description for the timeline node (max 60 chars)
        const briefDescription = item.title_or_summary 
          ? (item.title_or_summary.length > 60 ? item.title_or_summary.substring(0, 60) + '...' : item.title_or_summary)
          : 'Evidence item';
        
        return {
          id: evidenceId,
          type: 'evidence' as const,
          date: item.evidence_date || new Date().toISOString(),
          title: briefDescription, // Brief description for the node
          fullTitle: item.title_or_summary || 'Evidence item', // Full title for selected details
          fullText: item.description_or_details || 'No further details provided.', // Required field
          sourceUrl: item.source_url || '',
          evidenceSourceType: item.evidence_source_type || 'Evidence' // Pass the source type
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
      setSelectedEvent(events[events.length - 1]);
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
    <div className="my-6">      
      {/* Horizontal Timeline Section - visible on md screens and up */}
      <div className="hidden md:block mt-6 px-4 py-4 border border-gray-100 bg-gray-50 relative overflow-hidden">
        <div className="overflow-x-auto pb-2" style={{ maxWidth: "100%", overflowY: "hidden" }} ref={timelineRef}>
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
                <li key={event.id} className={`${liClass}`} data-event-id={event.id}>
                  {!isFirstEvent && <hr className="bg-gray-500 opacity-75" />}
                  <div className="timeline-middle">
                    <div className={`w-4 h-4 rounded-full bg-gray-500 opacity-75`}></div>
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
                  {!isLastEvent && <hr className="bg-gray-500 opacity-75" />} 
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
        <div className="mt-4">
          <p className="text-xs text-gray-500 mb-1">{formatDate(selectedEvent.date)}</p>
          <p className="font-medium text-gray-800 mb-1 text-md">{selectedEvent.fullTitle}</p>
          <p className="text-gray-600 text-sm whitespace-pre-wrap mb-3">{selectedEvent.fullText}</p>
          {selectedEvent.sourceUrl && (
            <a 
              href={selectedEvent.sourceUrl} 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-blue-600 hover:text-blue-800 hover:underline text-xs font-mono inline-flex items-center gap-1"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 inline-block" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M18 13v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6m5-3h3m0 0v6m0-6L10 14" />
              </svg>
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