'use client';

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogDescription, DialogClose } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from '@/components/ui/textarea';
import { Search, Edit3, PlusCircle, Filter, XCircle, AlertCircle } from 'lucide-react';
import { useSession } from '@/context/SessionContext';

// Define interfaces for promise data and search filters
interface PromiseData {
  id: string;
  text: string;
  source_type: string;
  bc_promise_rank?: 'strong' | 'medium' | 'weak' | null;
  bc_promise_direction?: string | null;
  bc_promise_rank_rationale?: string | null;
  parliament_session_id?: string;
  responsible_department_lead?: string;
  reporting_lead_title?: string;
  category?: string;
  date_issued?: string;
  progress_score?: number;
  progress_summary?: string;
  concise_title?: string;
  description?: string;
  what_it_means_for_canadians?: string;
  intended_impact_and_objectives?: string;
  background_and_context?: string;
  region_code?: string;
  party_code?: string;
  status?: 'active' | 'deleted';
  deleted_at?: string;
  deleted_by_admin?: string;
  // Add other relevant fields from your Firestore promise documents
  department?: string;
  [key: string]: any; // Allow other fields
}

interface SearchFilters {
  source_type: string;
  bc_promise_rank: string;
  searchText: string;
}

// Define field types and validation rules
const FIELD_CONFIG = {
  // Define the order in which fields should appear in the edit modal
  fieldOrder: [
    // Core promise content (most important)
    'text',
    'concise_title',
    'description',

    // Classification and ranking
    'bc_promise_rank',
    'bc_promise_direction',
    'bc_promise_rank_rationale',
    'source_type',

    // Administrative details
    'responsible_department_lead',
    'reporting_lead_title',
    'category',
    'parliament_session_id',
    'date_issued',
    'status',

    // Progress tracking
    'progress_score',
    'progress_summary',

    // Detailed explanations
    'what_it_means_for_canadians',
    'intended_impact_and_objectives',
    'background_and_context',

    // Data relationships
    'linked_evidence_ids',
    'commitment_history_rationale',

    // Any other fields not explicitly listed will appear at the end
  ],

  // Read-only fields that shouldn't be editable
  readOnly: ['id', 'region_code', 'party_code', 'migration_metadata', 'ingested_at', 'explanation_enriched_at', 'linking_preprocessing_done_at'],

  // Text area fields for longer content
  textArea: [
    'text',
    'description',
    'what_it_means_for_canadians',
    'intended_impact_and_objectives',
    'background_and_context',
    'bc_promise_rank_rationale',
    'progress_summary',
    'concise_title'
  ],

  // Select/dropdown fields with predefined options
  select: {
    bc_promise_rank: [
      { value: 'strong', label: 'Strong' },
      { value: 'medium', label: 'Medium' },
      { value: 'weak', label: 'Weak' },
      { value: null, label: 'N/A (Not Ranked)' }
    ],
    bc_promise_direction: [
      { value: 'positive', label: 'Positive' },
      { value: 'negative', label: 'Negative' },
      { value: 'neutral', label: 'Neutral' },
      { value: null, label: 'N/A (Not Set)' }
    ],
    source_type: [
      { value: 'platform', label: 'Platform' },
      { value: 'mandate_letter', label: 'Mandate Letter' },
      { value: 'speech_from_throne', label: 'Speech from Throne' },
      { value: 'budget', label: 'Budget' },
      { value: 'announcement', label: 'Announcement' },
      { value: 'other', label: 'Other' }
    ],
    status: [
      { value: 'active', label: 'Active' },
      { value: 'deleted', label: 'Deleted' }
    ]
  },

  // Number fields that should only accept numeric input
  number: ['progress_score'],

  // Date fields (ISO date strings)
  date: ['date_issued'],

  // Boolean fields
  boolean: [],

  // Array fields (will be displayed as JSON)
  array: ['linked_evidence_ids', 'commitment_history_rationale'],

  // Special fields that should be treated as regular text inputs
  text: [
    'responsible_department_lead',
    'reporting_lead_title',
    'category',
    'parliament_session_id'
  ]
};

export default function ManagePromisesPage() {
  const { currentSessionId, isLoadingSessions } = useSession();
  const [allFetchedPromises, setAllFetchedPromises] = useState<PromiseData[]>([]);
  const [filters, setFilters] = useState<SearchFilters>({
    source_type: 'all',
    bc_promise_rank: 'all',
    searchText: ''
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedPromise, setSelectedPromise] = useState<PromiseData | null>(null);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [isAddEvidenceOpen, setIsAddEvidenceOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [promiseToDelete, setPromiseToDelete] = useState<PromiseData | null>(null);
  const [evidenceUrl, setEvidenceUrl] = useState('');
  const [editablePromiseData, setEditablePromiseData] = useState<PromiseData | null>(null);
  const [availableSourceTypes, setAvailableSourceTypes] = useState<string[]>(['all']);
  const [availableRanks, setAvailableRanks] = useState<string[]>(['all', 'strong', 'medium', 'weak', 'none']);
  const [totalRecords, setTotalRecords] = useState(0);

  const isInitialMount = useRef(true);

  const fetchAndSetPromises = useCallback(async (currentFilters: SearchFilters, explicitLimit?: number) => {
    if (!currentSessionId) {
      console.log('No current session ID available, skipping fetch');
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const queryParams = new URLSearchParams();

      // Always filter by current parliament session
      queryParams.append('parliament_session_id', currentSessionId);

      if (currentFilters.source_type && currentFilters.source_type !== 'all') {
        queryParams.append('source_type', currentFilters.source_type);
      }
      if (currentFilters.bc_promise_rank && currentFilters.bc_promise_rank !== 'all') {
        queryParams.append('bc_promise_rank', currentFilters.bc_promise_rank);
      }
      if (explicitLimit) {
        queryParams.append('limit', explicitLimit.toString());
      }

      const response = await fetch(`/api/admin/promises?${queryParams.toString()}`);
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `Failed to fetch promises: ${response.statusText}`);
      }
      const data = await response.json();
      const fetchedPromises: PromiseData[] = data.promises || [];
      setAllFetchedPromises(fetchedPromises);
      if (data.total !== undefined) {
        setTotalRecords(data.total);
      } else if (explicitLimit === 5000 && !currentFilters.source_type && !currentFilters.bc_promise_rank) {
        setTotalRecords(fetchedPromises.length);
      }

    } catch (e: any) {
      console.error("Error fetching promises:", e);
      setError(e.message || "An unknown error occurred while fetching promises.");
      setAllFetchedPromises([]);
      setAvailableSourceTypes(['all']);
      setTotalRecords(0);
    }
    setIsLoading(false);
  }, [currentSessionId]);

  useEffect(() => {
    if (!currentSessionId || isLoadingSessions) return;

    setIsLoading(true);
    setError(null);
    const queryParams = new URLSearchParams();
    queryParams.append('parliament_session_id', currentSessionId);
    queryParams.append('limit', '5000');

    fetch(`/api/admin/promises?${queryParams.toString()}`)
      .then(response => {
        if (!response.ok) return response.json().then(err => { throw new Error(err.error || `Failed to fetch initial data: ${response.statusText}`) });
        return response.json();
      })
      .then(data => {
        const allPromisesInitial: PromiseData[] = data.promises || [];
        setAllFetchedPromises(allPromisesInitial);
        if (data.total !== undefined) {
          setTotalRecords(data.total);
        } else {
          setTotalRecords(allPromisesInitial.length);
        }

        const uniqueSourceTypes = Array.from(new Set(allPromisesInitial.map(p => p.source_type).filter(Boolean)));
        setAvailableSourceTypes(['all', ...uniqueSourceTypes.sort()]);

        const uniqueRanks = Array.from(new Set(allPromisesInitial.map(p => p.bc_promise_rank).filter(r => r !== null && r !== undefined))) as string[];
        setAvailableRanks(['all', ...uniqueRanks.sort(), 'none']);
      })
      .catch(e => {
        console.error("Error on initial data load:", e);
        setError(e.message || "An unknown error occurred during initial data load.");
        setAvailableSourceTypes(['all']);
        setAvailableRanks(['all', 'strong', 'medium', 'weak', 'none']);
        setTotalRecords(0);
      })
      .finally(() => setIsLoading(false));
  }, [currentSessionId, isLoadingSessions]);

  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }

    if (!currentSessionId) return;

    if (filters.source_type === 'all' && filters.bc_promise_rank === 'all') {
      fetchAndSetPromises(filters, 5000);
    } else if (filters.source_type !== 'all' || filters.bc_promise_rank !== 'all') {
      fetchAndSetPromises(filters);
    }
  }, [filters.source_type, filters.bc_promise_rank, fetchAndSetPromises, currentSessionId]);

  const displayedPromises = useMemo(() => {
    let filtered = [...allFetchedPromises];

    if (filters.source_type !== 'all') {
      filtered = filtered.filter(p => p.source_type === filters.source_type);
    }
    if (filters.bc_promise_rank !== 'all') {
      if (filters.bc_promise_rank === 'none') {
        filtered = filtered.filter(p => p.bc_promise_rank === null || p.bc_promise_rank === undefined);
      } else {
        filtered = filtered.filter(p => p.bc_promise_rank === filters.bc_promise_rank);
      }
    }

    if (filters.searchText) {
      const lowerSearchText = filters.searchText.toLowerCase();
      filtered = filtered.filter(p =>
        p.text.toLowerCase().includes(lowerSearchText) ||
        p.id.toLowerCase().includes(lowerSearchText)
      );
    }
    return filtered;
  }, [allFetchedPromises, filters]);

  const handleFilterChange = (filterName: keyof SearchFilters, value: string) => {
    setFilters(prev => ({ ...prev, [filterName]: value }));
  };

  const handleSearch = () => {
    console.log("Applying filters (API for dropdowns, client for text search):", filters);
    if (filters.source_type === 'all' && filters.bc_promise_rank === 'all') {
      fetchAndSetPromises(filters, 5000);
    } else {
      fetchAndSetPromises(filters);
    }
  };

  const clearFilters = () => {
    const cleared = { source_type: 'all', bc_promise_rank: 'all', searchText: '' };
    setFilters(cleared);
  };

  const handleEdit = (promise: PromiseData) => {
    setSelectedPromise(promise);
    setEditablePromiseData({ ...promise });
    console.log('Available fields for editing:', Object.keys(promise));
    console.log('Promise data:', promise);
    setIsEditDialogOpen(true);
  };

  const handleSaveEdit = async () => {
    if (!editablePromiseData || !editablePromiseData.id) {
      setError("No promise data to save or promise ID is missing.");
      return;
    }
    setIsLoading(true);
    setError(null);

    try {
      // Exclude 'id' from the payload as it's part of the URL
      const { id, ...updatePayload } = editablePromiseData;

      console.log('Saving promise with ID:', id);
      console.log('Update payload:', updatePayload);

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/admin/promises/${id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updatePayload),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error', details: `HTTP ${response.status}` }));
        console.error('API Error Response:', errorData);
        throw new Error(errorData.details || errorData.error || `Failed to save promise: ${response.statusText} (Status: ${response.status})`);
      }

      const responseData = await response.json();
      console.log('Save successful:', responseData);

      // Successfully saved to API
      setIsEditDialogOpen(false);
      setEditablePromiseData(null);

      // Re-fetch promises to reflect changes and ensure data consistency
      // Determine if we need the large limit based on current filters
      const shouldUseLargeLimit = filters.source_type === 'all' && filters.bc_promise_rank === 'all';
      await fetchAndSetPromises(filters, shouldUseLargeLimit ? 5000 : undefined);

      console.log("Promise updated successfully!");

    } catch (e: any) {
      console.error("Error saving promise:", e);
      setError(`Failed to save promise: ${e.message}`);
    }
    setIsLoading(false);
  };

  const validateAndSetFieldValue = (field: keyof PromiseData, value: any) => {
    if (!editablePromiseData) return;

    let validatedValue = value;
    const fieldStr = String(field);

    // Validate based on field type
    if (FIELD_CONFIG.number.includes(fieldStr)) {
      // For number fields, ensure the value is a valid number or null/empty
      if (value === '' || value === null || value === undefined) {
        validatedValue = null;
      } else {
        const numValue = parseFloat(value);
        if (isNaN(numValue)) {
          // Invalid number, don't update
          return;
        }
        validatedValue = numValue;
      }
    } else if (FIELD_CONFIG.date.includes(fieldStr)) {
      // For date fields, validate ISO date format
      if (value && value !== '') {
        try {
          const date = new Date(value);
          if (isNaN(date.getTime())) {
            // Invalid date, don't update
            return;
          }
          validatedValue = value;
        } catch (e) {
          // Invalid date format, don't update
          return;
        }
      } else {
        validatedValue = null;
      }
    } else if (FIELD_CONFIG.array.includes(fieldStr)) {
      // For array fields, try to parse JSON
      if (value && value !== '') {
        try {
          const parsed = JSON.parse(value);
          if (Array.isArray(parsed)) {
            validatedValue = parsed;
          } else {
            // Not an array, don't update
            return;
          }
        } catch (e) {
          // Invalid JSON, don't update
          return;
        }
      } else {
        validatedValue = [];
      }
    }

    setEditablePromiseData(prev => prev ? { ...prev, [field]: validatedValue } : null);
  };

  const renderEditField = (key: string, value: any) => {
    if (FIELD_CONFIG.readOnly.includes(key)) {
      return null; // Don't render read-only fields
    }

    const label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    const displayValue = value === null || value === undefined ? '' : value;

    if (FIELD_CONFIG.textArea.includes(key)) {
      return (
        <div className="grid grid-cols-4 items-start gap-4" key={key}>
          <Label htmlFor={key} className="text-right col-span-1 pt-2">{label}</Label>
          <Textarea
            id={key}
            value={displayValue as string}
            onChange={(e) => validateAndSetFieldValue(key as keyof PromiseData, e.target.value)}
            className="col-span-3"
            rows={key === 'text' ? 4 : 3}
            disabled={isLoading}
          />
        </div>
      );
    }

    if (FIELD_CONFIG.select[key as keyof typeof FIELD_CONFIG.select]) {
      const options = FIELD_CONFIG.select[key as keyof typeof FIELD_CONFIG.select];
      const selectValue = value === null || value === undefined ? 'null' : value;

      return (
        <div className="grid grid-cols-4 items-center gap-4" key={key}>
          <Label htmlFor={key} className="text-right col-span-1">{label}</Label>
          <Select
            value={selectValue as string}
            onValueChange={(val) => validateAndSetFieldValue(key as keyof PromiseData, val === 'null' ? null : val)}
            disabled={isLoading}
          >
            <SelectTrigger className="col-span-3"><SelectValue placeholder={`Select ${label}`} /></SelectTrigger>
            <SelectContent>
              {options.map(option => (
                <SelectItem key={option.value || 'null'} value={option.value || 'null'}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      );
    }

    if (FIELD_CONFIG.number.includes(key)) {
      return (
        <div className="grid grid-cols-4 items-center gap-4" key={key}>
          <Label htmlFor={key} className="text-right col-span-1">{label}</Label>
          <Input
            id={key}
            type="number"
            step={key === 'progress_score' ? 1 : 1}
            min={key === 'progress_score' ? 0 : undefined}
            max={key === 'progress_score' ? 5 : undefined}
            value={displayValue === null ? '' : displayValue}
            onChange={(e) => validateAndSetFieldValue(key as keyof PromiseData, e.target.value)}
            className="col-span-3"
            disabled={isLoading}
            placeholder={key === 'progress_score' ? '0-5' : 'Enter number'}
          />
        </div>
      );
    }

    if (FIELD_CONFIG.date.includes(key)) {
      return (
        <div className="grid grid-cols-4 items-center gap-4" key={key}>
          <Label htmlFor={key} className="text-right col-span-1">{label}</Label>
          <Input
            id={key}
            type="date"
            value={displayValue}
            onChange={(e) => validateAndSetFieldValue(key as keyof PromiseData, e.target.value)}
            className="col-span-3"
            disabled={isLoading}
          />
        </div>
      );
    }

    if (FIELD_CONFIG.array.includes(key)) {
      const jsonValue = Array.isArray(displayValue) ? JSON.stringify(displayValue, null, 2) : displayValue;
      return (
        <div className="grid grid-cols-4 items-start gap-4" key={key}>
          <Label htmlFor={key} className="text-right col-span-1 pt-2">{label}</Label>
          <Textarea
            id={key}
            value={jsonValue}
            onChange={(e) => validateAndSetFieldValue(key as keyof PromiseData, e.target.value)}
            className="col-span-3 font-mono text-sm"
            rows={3}
            disabled={isLoading}
            placeholder="[]"
          />
        </div>
      );
    }

    if (FIELD_CONFIG.text.includes(key)) {
      return (
        <div className="grid grid-cols-4 items-center gap-4" key={key}>
          <Label htmlFor={key} className="text-right col-span-1">{label}</Label>
          <Input
            id={key}
            value={displayValue}
            onChange={(e) => validateAndSetFieldValue(key as keyof PromiseData, e.target.value)}
            className="col-span-3"
            disabled={isLoading}
            placeholder={`Enter ${label.toLowerCase()}`}
          />
        </div>
      );
    }

    // Default to text input for any other fields not explicitly configured
    return (
      <div className="grid grid-cols-4 items-center gap-4" key={key}>
        <Label htmlFor={key} className="text-right col-span-1">{label}</Label>
        <Input
          id={key}
          value={typeof displayValue === 'string' || typeof displayValue === 'number' ? displayValue : JSON.stringify(displayValue)}
          onChange={(e) => validateAndSetFieldValue(key as keyof PromiseData, e.target.value)}
          className="col-span-3"
          disabled={isLoading}
          placeholder="Enter value"
        />
      </div>
    );
  };

  const handleAddEvidence = (promise: PromiseData) => {
    setSelectedPromise(promise);
    setEvidenceUrl('');
    setIsAddEvidenceOpen(true);
  };

  const handleDelete = (promise: PromiseData) => {
    setPromiseToDelete(promise);
    setIsDeleteDialogOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!promiseToDelete) return;

    setIsLoading(true);
    setError(null);

    try {
      console.log('Deleting promise:', promiseToDelete.id);

      const response = await fetch(`/api/admin/promises/${promiseToDelete.id}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error', details: `HTTP ${response.status}` }));
        console.error('Delete API Error Response:', errorData);
        throw new Error(errorData.details || errorData.error || `Failed to delete promise: ${response.statusText}`);
      }

      const responseData = await response.json();
      console.log('Delete successful:', responseData);

      // Close dialog and reset state
      setIsDeleteDialogOpen(false);
      setPromiseToDelete(null);

      // Re-fetch promises to reflect changes
      const shouldUseLargeLimit = filters.source_type === 'all' && filters.bc_promise_rank === 'all';
      await fetchAndSetPromises(filters, shouldUseLargeLimit ? 5000 : undefined);

      console.log("Promise deleted successfully!");

    } catch (e: any) {
      console.error("Error deleting promise:", e);
      setError(`Failed to delete promise: ${e.message}`);
    }
    setIsLoading(false);
  };

  const handleSubmitEvidence = async () => {
    if (!selectedPromise) return;
    console.log('Submitting evidence URL:', evidenceUrl, 'for promise:', selectedPromise.id);
    // TODO: Implement API call
    setIsAddEvidenceOpen(false);
    setEvidenceUrl('');
  };

  if (isLoadingSessions) {
    return <div className="text-center py-4">Loading parliament sessions...</div>;
  }

  if (!currentSessionId) {
    return <div className="text-center py-4 text-red-600">No current parliament session available. Please check your session configuration.</div>;
  }

  return (
    <div className="space-y-6">
      <div className="rounded-lg border bg-card text-card-foreground shadow-sm p-6 space-y-4">
        <h2 className="text-xl font-semibold flex items-center">
          <Filter className="mr-2 h-5 w-5" />
          Filters & Search
          <span className="ml-4 text-sm font-normal text-gray-600">
            (Parliament Session: {currentSessionId})
          </span>
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Select value={filters.source_type} onValueChange={(value) => handleFilterChange('source_type', value)} disabled={isLoading}>
            <SelectTrigger><SelectValue placeholder="Source Type" /></SelectTrigger>
            <SelectContent>
              {availableSourceTypes.map(st => <SelectItem key={st} value={st}>{st === 'all' ? 'All Source Types' : st}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={filters.bc_promise_rank} onValueChange={(value) => handleFilterChange('bc_promise_rank', value)} disabled={isLoading}>
            <SelectTrigger><SelectValue placeholder="BC Promise Rank" /></SelectTrigger>
            <SelectContent>
              {availableRanks.map(rank => <SelectItem key={rank} value={rank}>{rank === 'all' ? 'All Ranks' : (rank === 'none' ? 'Not Ranked' : rank.charAt(0).toUpperCase() + rank.slice(1))}</SelectItem>)}
            </SelectContent>
          </Select>
          <Input
            type="text"
            placeholder="Search in text or ID (client-side)..."
            value={filters.searchText}
            onChange={(e) => handleFilterChange('searchText', e.target.value)}
            className="md:col-span-1"
            disabled={isLoading}
          />
        </div>
        <div className="flex justify-end space-x-2">
          <Button variant="outline" onClick={clearFilters} className="flex items-center" disabled={isLoading}>
            <XCircle className="mr-2 h-4 w-4" /> Clear Filters
          </Button>
          <Button onClick={handleSearch} className="flex items-center bg-[#8b2332] hover:bg-[#721c28] text-white" disabled={isLoading}>
            {isLoading ? 'Loading...' : <><Search className="mr-2 h-4 w-4" /> Apply Filters</>}
          </Button>
        </div>
      </div>

      {error && (
        <div className="flex items-center p-4 mb-4 text-sm text-red-800 border border-red-300 rounded-lg bg-red-50 dark:text-red-400 dark:border-red-800" role="alert">
          <AlertCircle className="flex-shrink-0 inline w-4 h-4 mr-3" />
          <span className="font-medium">Error:</span> {error}
        </div>
      )}

      {!isLoading && !error && (
        <div className="text-sm text-gray-600 px-1 py-2">
          Showing {displayedPromises.length} of {totalRecords > 0 ? totalRecords : (allFetchedPromises.length > 0 ? allFetchedPromises.length : 'many')} records.
          {(filters.source_type !== 'all' || filters.bc_promise_rank !== 'all' || filters.searchText) && totalRecords > 0 && displayedPromises.length < totalRecords && displayedPromises.length > 0 ?
            ` (Filtered from ${totalRecords} total records in current view criteria)` : ''}
          {totalRecords > 0 && allFetchedPromises.length === 5000 && displayedPromises.length === 5000 && !filters.searchText && (filters.source_type === 'all' && filters.bc_promise_rank === 'all') &&
            ' (Initial display limit of 5000 reached, more records matching this view might exist in the database)'}
        </div>
      )}

      {isLoading && !error && displayedPromises.length === 0 && <p className="text-center py-4">Loading promises...</p>}
      {!isLoading && !error && displayedPromises.length === 0 && (
        <div className="text-center py-10">
          <p className="text-gray-500">
            {(filters.searchText || filters.source_type !== 'all' || filters.bc_promise_rank !== 'all') ? 'No promises found matching your criteria.' : 'No promises to display. Try applying filters or searching.'}
          </p>
        </div>
      )}
      {!isLoading && !error && displayedPromises.length > 0 && (
        <div className="rounded-lg border bg-card text-card-foreground shadow-sm">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Promise Text</TableHead>
                <TableHead>Source Type</TableHead>
                <TableHead>BC Rank</TableHead>
                <TableHead>BC Direction</TableHead>
                <TableHead>Department</TableHead>
                <TableHead>Progress</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-[140px] text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {displayedPromises.map((promise) => (
                <TableRow key={promise.id} className={promise.status === 'deleted' ? 'opacity-60 bg-red-50' : ''}>
                  <TableCell className="font-medium text-xs">{promise.id}</TableCell>
                  <TableCell className="text-xs max-w-md truncate" title={promise.text}>
                    {promise.status === 'deleted' && <span className="text-red-600 font-medium">[DELETED] </span>}
                    {promise.text}
                  </TableCell>
                  <TableCell className="text-xs">{promise.source_type}</TableCell>
                  <TableCell className="text-xs">
                    {promise.bc_promise_rank ?
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium 
                            ${promise.bc_promise_rank === 'strong' ? 'bg-green-100 text-green-700' :
                          promise.bc_promise_rank === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                            promise.bc_promise_rank === 'weak' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-600'}
                        `}>
                        {promise.bc_promise_rank.charAt(0).toUpperCase() + promise.bc_promise_rank.slice(1)}
                      </span>
                      : 'N/A'}
                  </TableCell>
                  <TableCell className="text-xs">
                    {promise.bc_promise_direction ?
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium 
                            ${promise.bc_promise_direction === 'positive' ? 'bg-green-100 text-green-700' :
                          promise.bc_promise_direction === 'negative' ? 'bg-red-100 text-red-700' :
                            promise.bc_promise_direction === 'neutral' ? 'bg-gray-100 text-gray-700' : 'bg-gray-100 text-gray-600'}
                        `}>
                        {promise.bc_promise_direction.charAt(0).toUpperCase() + promise.bc_promise_direction.slice(1)}
                      </span>
                      : 'N/A'}
                  </TableCell>
                  <TableCell className="text-xs">{promise.responsible_department_lead || 'N/A'}</TableCell>
                  <TableCell className="text-xs">
                    {promise.progress_score !== undefined && promise.progress_score !== null ?
                      `${promise.progress_score}` : 'N/A'}
                  </TableCell>
                  <TableCell className="text-xs">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium 
                        ${promise.status === 'deleted' ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}
                    `}>
                      {promise.status === 'deleted' ? 'Deleted' : 'Active'}
                    </span>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end space-x-1">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleEdit(promise)}
                        className="h-7 px-2"
                        disabled={isLoading || isEditDialogOpen}
                        title="Edit Promise"
                      >
                        <Edit3 className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleAddEvidence(promise)}
                        className="h-7 px-2"
                        disabled={isLoading || isAddEvidenceOpen || promise.status === 'deleted'}
                        title="Add Evidence"
                      >
                        <PlusCircle className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleDelete(promise)}
                        className="h-7 px-2 hover:bg-red-50 hover:border-red-200"
                        disabled={isLoading || isDeleteDialogOpen || promise.status === 'deleted'}
                        title={promise.status === 'deleted' ? 'Already Deleted' : 'Delete Promise'}
                      >
                        <XCircle className="h-3.5 w-3.5 text-red-600" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {selectedPromise && editablePromiseData && (
        <Dialog open={isEditDialogOpen} onOpenChange={(isOpen) => { if (isLoading && isOpen) return; setIsEditDialogOpen(isOpen); if (!isOpen) setSelectedPromise(null); }}>
          <DialogContent className="sm:max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
            <DialogHeader>
              <DialogTitle>Edit Promise: {selectedPromise.id}</DialogTitle>
              <DialogDescription>Modify the details of the promise below. Fields are validated based on their expected data type. Click save when you're done.</DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4 overflow-y-auto pr-2 flex-1">
              {/* Render fields in the specified order */}
              {FIELD_CONFIG.fieldOrder.map(key => {
                if (editablePromiseData && editablePromiseData.hasOwnProperty(key)) {
                  return renderEditField(key, editablePromiseData[key]);
                }
                return null;
              })}

              {/* Render any additional fields not in the fieldOrder */}
              {editablePromiseData && Object.keys(editablePromiseData)
                .filter(key => !FIELD_CONFIG.fieldOrder.includes(key))
                .map(key => renderEditField(key, editablePromiseData[key]))
              }
            </div>
            <DialogFooter>
              <DialogClose asChild>
                <Button type="button" variant="outline" disabled={isLoading}>Cancel</Button>
              </DialogClose>
              <Button type="button" onClick={handleSaveEdit} className="bg-[#8b2332] hover:bg-[#721c28] text-white" disabled={isLoading}>{isLoading ? 'Saving...' : 'Save Changes'}</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

      {selectedPromise && (
        <Dialog open={isAddEvidenceOpen} onOpenChange={(isOpen) => { if (isLoading && isOpen) return; setIsAddEvidenceOpen(isOpen); if (!isOpen) setSelectedPromise(null); }}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Add Evidence for: {selectedPromise.id}</DialogTitle>
              <DialogDescription>
                Enter the URL of the evidence you want to link to this promise. It will be processed and reviewed.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="evidence-url" className="text-right col-span-1">
                  Evidence URL
                </Label>
                <Input
                  id="evidence-url"
                  value={evidenceUrl}
                  onChange={(e) => setEvidenceUrl(e.target.value)}
                  className="col-span-3"
                  placeholder="https://example.com/evidence_page"
                  disabled={isLoading}
                />
              </div>
              <p className="text-xs text-gray-500 px-1">
                Example: <span className="italic">{selectedPromise.text.substring(0, 50)}...</span>
              </p>
            </div>
            <DialogFooter>
              <DialogClose asChild>
                <Button type="button" variant="outline" disabled={isLoading}>Cancel</Button>
              </DialogClose>
              <Button type="button" onClick={handleSubmitEvidence} className="bg-[#8b2332] hover:bg-[#721c28] text-white" disabled={isLoading}>
                {isLoading ? 'Submitting...' : 'Submit URL'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

      {promiseToDelete && (
        <Dialog open={isDeleteDialogOpen} onOpenChange={(isOpen) => { if (isLoading && isOpen) return; setIsDeleteDialogOpen(isOpen); if (!isOpen) setPromiseToDelete(null); }}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center text-red-600">
                <AlertCircle className="h-5 w-5 mr-2" />
                Confirm Delete
              </DialogTitle>
              <DialogDescription>
                Are you sure you want to delete this promise? This action will mark it as deleted but can be reversed later if needed.
              </DialogDescription>
            </DialogHeader>
            <div className="py-4">
              <div className="bg-gray-50 p-3 rounded-md">
                <p className="text-sm font-medium text-gray-900">Promise ID: {promiseToDelete.id}</p>
                <p className="text-sm text-gray-600 mt-1 line-clamp-3">
                  {promiseToDelete.text.substring(0, 150)}...
                </p>
              </div>
            </div>
            <DialogFooter>
              <DialogClose asChild>
                <Button type="button" variant="outline" disabled={isLoading}>Cancel</Button>
              </DialogClose>
              <Button
                type="button"
                onClick={handleConfirmDelete}
                className="bg-red-600 hover:bg-red-700 text-white"
                disabled={isLoading}
              >
                {isLoading ? 'Deleting...' : 'Delete Promise'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
} 