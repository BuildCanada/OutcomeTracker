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

// Define interfaces for promise data and search filters
interface PromiseData {
  id: string;
  text: string;
  source_type: string;
  bc_promise_rank?: 'strong' | 'medium' | 'weak' | null;
  // Add other relevant fields from your Firestore promise documents
  department?: string;
  status?: string;
  [key: string]: any; // Allow other fields
}

interface SearchFilters {
  source_type: string;
  bc_promise_rank: string;
  searchText: string;
}

export default function ManagePromisesPage() {
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
  const [evidenceUrl, setEvidenceUrl] = useState('');
  const [editablePromiseData, setEditablePromiseData] = useState<PromiseData | null>(null);
  const [availableSourceTypes, setAvailableSourceTypes] = useState<string[]>(['all']);
  const [availableRanks, setAvailableRanks] = useState<string[]>(['all', 'strong', 'medium', 'weak', 'none']);
  const [totalRecords, setTotalRecords] = useState(0);

  const isInitialMount = useRef(true);

  const fetchAndSetPromises = useCallback(async (currentFilters: SearchFilters, explicitLimit?: number) => {
    setIsLoading(true);
    setError(null);
    try {
      const queryParams = new URLSearchParams();
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
      } else if (!queryParams.has('source_type') && !queryParams.has('bc_promise_rank') && !queryParams.has('searchText')) {
      }

    } catch (e: any) {
      console.error("Error fetching promises:", e);
      setError(e.message || "An unknown error occurred while fetching promises.");
      setAllFetchedPromises([]);
      setAvailableSourceTypes(['all']); 
      setTotalRecords(0);
    }
    setIsLoading(false);
  }, []);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    const queryParams = new URLSearchParams(); 
    queryParams.append('limit', '5000'); 

    fetch(`/api/admin/promises?${queryParams.toString()}`)
      .then(response => {
        if (!response.ok) return response.json().then(err => { throw new Error(err.error || `Failed to fetch initial data: ${response.statusText}`)}); 
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
  }, [fetchAndSetPromises]);


  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return; 
    }

    if (filters.source_type === 'all' && filters.bc_promise_rank === 'all') {
      fetchAndSetPromises(filters, 5000);
    } else if (filters.source_type !== 'all' || filters.bc_promise_rank !== 'all') {
      fetchAndSetPromises(filters);
    }
  }, [filters.source_type, filters.bc_promise_rank, fetchAndSetPromises]);


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
    setIsEditDialogOpen(true);
  };

  const handleSaveEdit = async () => {
    if (!editablePromiseData) return;
    setIsLoading(true);
    try {
      console.log('Saving promise:', editablePromiseData);
      // TODO: Implement API call (e.g., PUT /api/admin/promises/[promiseId])
      const updatedPromises = allFetchedPromises.map(p => p.id === editablePromiseData.id ? { ...editablePromiseData } : p);
      setAllFetchedPromises(updatedPromises);
            
      setIsEditDialogOpen(false);
      setEditablePromiseData(null);

    } catch (e: any) {
      console.error("Error saving promise:", e);
      setError("Failed to save promise: " + e.message);
    }
    setIsLoading(false);
  };

  const handleEditableFieldChange = (field: keyof PromiseData, value: any) => {
    if (editablePromiseData) {
      setEditablePromiseData(prev => prev ? { ...prev, [field]: value } : null);
    }
  };

  const handleAddEvidence = (promise: PromiseData) => {
    setSelectedPromise(promise);
    setEvidenceUrl('');
    setIsAddEvidenceOpen(true);
  };

  const handleSubmitEvidence = async () => {
    if (!selectedPromise) return;
    console.log('Submitting evidence URL:', evidenceUrl, 'for promise:', selectedPromise.id);
    // TODO: Implement API call
    setIsAddEvidenceOpen(false);
    setEvidenceUrl('');
  };
  
  return (
    <div className="space-y-6">
      <div className="rounded-lg border bg-card text-card-foreground shadow-sm p-6 space-y-4">
        <h2 className="text-xl font-semibold flex items-center"><Filter className="mr-2 h-5 w-5" /> Filters & Search</h2>
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
                <XCircle className="mr-2 h-4 w-4"/> Clear Filters
            </Button>
            <Button onClick={handleSearch} className="flex items-center bg-[#8b2332] hover:bg-[#721c28] text-white" disabled={isLoading}>
                {isLoading ? 'Loading...' : <><Search className="mr-2 h-4 w-4"/> Apply Filters</>}
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
                <TableHead className="w-[120px]">Actions</TableHead>
                <TableHead>ID</TableHead>
                <TableHead>Promise Text</TableHead>
                <TableHead>Source Type</TableHead>
                <TableHead>BC Rank</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {displayedPromises.map((promise) => (
                <TableRow key={promise.id}>
                  <TableCell className="space-x-1">
                    <Button variant="outline" size="sm" onClick={() => handleEdit(promise)} className="h-7 px-2" disabled={isLoading || isEditDialogOpen}>
                      <Edit3 className="h-3.5 w-3.5" />
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => handleAddEvidence(promise)} className="h-7 px-2" disabled={isLoading || isAddEvidenceOpen}>
                      <PlusCircle className="h-3.5 w-3.5" />
                    </Button>
                  </TableCell>
                  <TableCell className="font-medium text-xs">{promise.id}</TableCell>
                  <TableCell className="text-xs max-w-md truncate" title={promise.text}>{promise.text}</TableCell>
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
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {selectedPromise && editablePromiseData && (
        <Dialog open={isEditDialogOpen} onOpenChange={(isOpen) => { if (isLoading && isOpen) return; setIsEditDialogOpen(isOpen); if(!isOpen) setSelectedPromise(null);}}>
          <DialogContent className="sm:max-w-2xl">
            <DialogHeader>
              <DialogTitle>Edit Promise: {selectedPromise.id}</DialogTitle>
              <DialogDescription>Modify the details of the promise below. Click save when you're done.</DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4 max-h-[60vh] overflow-y-auto pr-2">
              {Object.keys(editablePromiseData).map(key => {
                if (key === 'id') return null; 
                const label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                let value = editablePromiseData[key];
                const displayValue = value === null || value === undefined ? '' : value;
                
                if (key === 'text' || key === 'bc_promise_rank_rationale') {
                  return (
                    <div className="grid grid-cols-4 items-center gap-4" key={key}>
                      <Label htmlFor={key} className="text-right col-span-1">{label}</Label>
                      <Textarea 
                        id={key} 
                        value={displayValue as string}
                        onChange={(e) => handleEditableFieldChange(key, e.target.value)} 
                        className="col-span-3"
                        rows={key === 'text' ? 4: 2}
                        disabled={isLoading}
                      />
                    </div>
                  );
                } else if (key === 'bc_promise_rank') {
                  return (
                    <div className="grid grid-cols-4 items-center gap-4" key={key}>
                      <Label htmlFor={key} className="text-right col-span-1">{label}</Label>
                      <Select value={displayValue as string} onValueChange={(val) => handleEditableFieldChange(key, val === '' ? null : val)} disabled={isLoading}>
                        <SelectTrigger className="col-span-3"><SelectValue placeholder={`Select ${label}`} /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="strong">Strong</SelectItem>
                          <SelectItem value="medium">Medium</SelectItem>
                          <SelectItem value="weak">Weak</SelectItem>
                          <SelectItem value="">N/A (Not Ranked)</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  );
                }
                return (
                  <div className="grid grid-cols-4 items-center gap-4" key={key}>
                    <Label htmlFor={key} className="text-right col-span-1">{label}</Label>
                    <Input 
                      id={key} 
                      value={(typeof displayValue === 'string' || typeof displayValue === 'number') ? displayValue : JSON.stringify(displayValue)} 
                      onChange={(e) => handleEditableFieldChange(key, e.target.value)} 
                      className="col-span-3" 
                      disabled={isLoading || (typeof displayValue === 'object' && displayValue !== '' && !Array.isArray(displayValue))}
                    />
                  </div>
                );
              })}
            </div>
            <DialogFooter>
              <DialogClose asChild>
                <Button type="button" variant="outline" disabled={isLoading}>Cancel</Button>
              </DialogClose>
              <Button type="button" onClick={handleSaveEdit} className="bg-[#8b2332] hover:bg-[#721c28] text-white" disabled={isLoading}>{isLoading ? 'Saving...': 'Save Changes'}</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

      {selectedPromise && (
        <Dialog open={isAddEvidenceOpen} onOpenChange={(isOpen) => { if (isLoading && isOpen) return; setIsAddEvidenceOpen(isOpen); if(!isOpen) setSelectedPromise(null);}}>
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
                Example: <span className="italic">{selectedPromise.text.substring(0,50)}...</span>
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
    </div>
  );
} 