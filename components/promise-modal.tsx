'use client'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"
import type { PromiseData, EvidenceItem, RationaleEvent } from "@/lib/types"
import { CalendarIcon, FileTextIcon, UsersIcon, LinkIcon } from "lucide-react" // Added LinkIcon
import { Timestamp } from 'firebase/firestore';

interface PromiseModalProps {
  promise: PromiseData;
  evidenceItems: EvidenceItem[];
  isOpen: boolean;
  onClose: () => void;
}

// Helper to format Firestore Timestamp or ISO string date
const formatDate = (date: Timestamp | string | undefined): string => {
    if (!date) return 'Date unknown';
    try {
        const jsDate = date instanceof Timestamp ? date.toDate() : new Date(date);
        return jsDate.toLocaleDateString('en-CA', { year: 'numeric', month: 'long', day: 'numeric' });
    } catch (e) {
        console.error("Error formatting date:", date, e);
        return typeof date === 'string' ? date : 'Invalid date'; // Fallback for unparsable strings
    }
};

// Helper to format YYYY-MM-DD date string
const formatSimpleDate = (dateString: string | undefined): string => {
    if (!dateString) return 'Date unknown';
    try {
        const [year, month, day] = dateString.split('-');
        const date = new Date(parseInt(year), parseInt(month) - 1, parseInt(day));
        return date.toLocaleDateString('en-CA', { year: 'numeric', month: 'long', day: 'numeric' });
    } catch (e) {
        console.error("Error formatting simple date:", dateString, e);
        return dateString; // Fallback
    }
}

export default function PromiseModal({ promise, evidenceItems, isOpen, onClose }: PromiseModalProps) {
  const { text, commitment_history_rationale, date_issued } = promise;

  // Sort evidence items by date, most recent first for display
  const sortedEvidence = [...evidenceItems].sort((a, b) => {
    const dateA = a.evidence_date instanceof Timestamp ? a.evidence_date.toMillis() : new Date(a.evidence_date).getTime();
    const dateB = b.evidence_date instanceof Timestamp ? b.evidence_date.toMillis() : new Date(b.evidence_date).getTime();
    // Handle potential invalid dates
    if (isNaN(dateA) && isNaN(dateB)) return 0;
    if (isNaN(dateA)) return 1; // Put invalid dates last
    if (isNaN(dateB)) return -1;
    return dateB - dateA; // Descending order
  });

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto bg-white p-0 border border-[#d3c7b9]">
        {/* Header */}
        <DialogHeader className="border-b border-[#d3c7b9] p-6">
          {/* Removed Badges for now */}
          <DialogTitle className="text-2xl font-bold text-[#222222]">{text}</DialogTitle>
          {date_issued && (
            <DialogDescription className="text-[#555555] mt-2">Announced: {formatSimpleDate(date_issued)}</DialogDescription>
          )}
        </DialogHeader>

        <div className="p-6 space-y-8">
          {/* Rationale Section (Replaces Related Bills) */}
          {commitment_history_rationale && commitment_history_rationale.length > 0 && (
            <section>
              <h3 className="text-xl font-bold text-[#222222] mb-4 flex items-center">
                <FileTextIcon className="mr-2 h-5 w-5 text-[#8b2332]" />
                Rationale: Preceding Events
              </h3>
              <div className="space-y-4">
                {commitment_history_rationale.map((event: RationaleEvent, index: number) => (
                  <div key={index} className="border border-[#d3c7b9] p-4 bg-[#f8f2ea]">
                    <p className="text-sm font-medium text-[#8b2332] mb-1">{formatSimpleDate(event.date)}</p>
                    <p className="text-[#333333] mb-2">{event.action}</p>
                    <a
                      href={event.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-[#0056b3] hover:underline inline-flex items-center"
                    >
                      <LinkIcon className="mr-1 h-3 w-3" /> Source
                    </a>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Impact on Canadians (Placeholder) */}
          <section className="border-t border-[#d3c7b9] pt-8">
            <h3 className="text-xl font-bold text-[#222222] mb-4 flex items-center">
              <UsersIcon className="mr-2 h-5 w-5 text-[#8b2332]" />
              Impact on Canadians
            </h3>
            <p className="text-[#333333] leading-relaxed">[Details on the expected or observed impact of this promise will be added here.]</p>
          </section>

          {/* Timeline Section (Using Evidence Items) */}
          <section className="border-t border-[#d3c7b9] pt-8">
            <h3 className="text-xl font-bold text-[#222222] mb-4 flex items-center">
              <CalendarIcon className="mr-2 h-5 w-5 text-[#8b2332]" />
              Timeline of Actions & Evidence
            </h3>
            {sortedEvidence.length > 0 ? (
              <div className="relative border-l-2 border-[#d3c7b9] pl-6 space-y-6">
                {sortedEvidence.map((item: EvidenceItem) => (
                  <div key={item.evidence_id} className="relative">
                    <div className="absolute -left-[30px] top-1 h-4 w-4 rounded-full bg-[#8b2332] border-2 border-white"></div>
                    <div className="mb-1 text-sm font-medium text-[#8b2332]">{formatDate(item.evidence_date)}</div>
                    <h4 className="font-bold text-[#222222]">{item.title_or_summary}</h4>
                    {item.description_or_details && (
                        <p className="text-[#333333] mt-1 mb-2 text-sm">{item.description_or_details}</p>
                    )}
                    {item.source_url && (
                      <a
                        href={item.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-[#0056b3] hover:underline inline-flex items-center"
                      >
                        <LinkIcon className="mr-1 h-3 w-3" /> Source
                      </a>
                    )}
                    <p className="text-xs text-gray-500 mt-1">Type: {item.evidence_source_type}</p>
                    {/* Optionally display other fields like status_impact_on_promise */}
                  </div>
                ))}
              </div>
            ) : (
                 <p className="text-[#555555] italic">No timeline events recorded yet for this promise.</p>
            )}
          </section>
        </div>
      </DialogContent>
    </Dialog>
  )
} 