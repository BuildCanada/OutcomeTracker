'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useSession } from '@/context/SessionContext';
import { getSourceTypeOptions, getSourceTypeKeyByLabel } from '@/lib/evidence-source-types';
import clsx from 'clsx';
import { Link, SquarePen, Search, Trash2, Plus, RotateCcw } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AlertCircle } from 'lucide-react';

// Define interfaces
interface PromiseData {
  id: string;
  text: string;
  source_type: string;
  bc_promise_rank?: 'strong' | 'medium' | 'weak' | null;
  concise_title?: string;
  category?: string;
  responsible_department_lead?: string;
  reporting_lead_title?: string;
  background_and_context?: string;
  [key: string]: any;
}

interface EvidenceItem {
  id: string;
  title_or_summary: string;
  description_or_details: string;
  evidence_source_type: string;
  evidence_source_type_key?: string;
  source_url: string;
  promise_ids?: string[];
  created_at: any;
  evidence_date?: any;
  confidence_score?: number;
  promise_linking_status?: string;
  linked_departments?: string[];
  [key: string]: any;
}

interface EvidenceFormData {
  source_url: string;
  title_or_summary: string;
  description_or_details: string;
  evidence_source_type: string;
  selected_promise_ids: string[];
}

// Get evidence source types from centralized configuration
const EVIDENCE_SOURCE_TYPES = getSourceTypeOptions();

export default function ManageEvidencePage() {
  const { currentSessionId, isLoadingSessions } = useSession();
  const [evidenceMode, setEvidenceMode] = useState<'edit' | 'create'>('edit');
  const [creationMode, setCreationMode] = useState<'automated' | 'manual'>('automated');
  const [formData, setFormData] = useState<EvidenceFormData>({
    source_url: '',
    title_or_summary: '',
    description_or_details: '',
    evidence_source_type: '',
    selected_promise_ids: []
  });
  
  // Evidence management state
  const [evidenceItems, setEvidenceItems] = useState<EvidenceItem[]>([]);
  const [evidenceSearchText, setEvidenceSearchText] = useState('');
  const [filteredEvidenceItems, setFilteredEvidenceItems] = useState<EvidenceItem[]>([]);
  const [selectedEvidenceItem, setSelectedEvidenceItem] = useState<EvidenceItem | null>(null);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceSearchPerformed, setEvidenceSearchPerformed] = useState(false);
  
  // Promise selection state
  const [promises, setPromises] = useState<PromiseData[]>([]);
  const [filteredPromises, setFilteredPromises] = useState<PromiseData[]>([]);
  const [promiseSearchText, setPromiseSearchText] = useState('');
  
  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [originalPromiseCount, setOriginalPromiseCount] = useState<number | undefined>(undefined);

  // Add state for filters
  const [rankFilter, setRankFilter] = useState('all');
  const [ministerFilter, setMinisterFilter] = useState('all');
  const [availableMinisters, setAvailableMinisters] = useState<string[]>(['all']);

  // Load promises when session changes
  // REMOVED: Don't load promises immediately - only load them when user searches for evidence
  // useEffect(() => {
  //   if (currentSessionId) {
  //     fetchPromises();
  //   }
  // }, [currentSessionId]);

  // REMOVED: This useEffect was causing performance issues by filtering promises on every state change
  // Promise filtering is now handled only when the Search button is clicked in handleSearch function
  
  // Clear search when switching away from edit mode
  useEffect(() => {
    if (evidenceMode !== 'edit') {
      setEvidenceSearchText('');
      setEvidenceItems([]);
      setEvidenceSearchPerformed(false);
      setSelectedEvidenceItem(null);
    }
  }, [evidenceMode]);

  // Clear form data when switching from edit to create mode
  useEffect(() => {
    if (evidenceMode === 'create' && selectedEvidenceItem) {
      // User switched from edit to create - clear all form data
      setFormData({
        source_url: '',
        title_or_summary: '',
        description_or_details: '',
        evidence_source_type: '',
        selected_promise_ids: []
      });
      setSelectedEvidenceItem(null);
      setOriginalPromiseCount(undefined);
      setError(null);
      setSuccess(null);
    }
  }, [evidenceMode, selectedEvidenceItem]);

  // Trigger promise search when selected promise IDs change in edit mode
  useEffect(() => {
    if (evidenceMode === 'edit' && selectedEvidenceItem && promises.length > 0) {
      handleSearch();
    }
  }, [formData.selected_promise_ids, evidenceMode, selectedEvidenceItem, promises.length]);

  const fetchPromises = async () => {
    try {
      const queryParams = new URLSearchParams();
      queryParams.append('parliament_session_id', currentSessionId!);
      queryParams.append('limit', '2000');

      const response = await fetch(`/api/admin/promises?${queryParams.toString()}`);
      if (!response.ok) {
        throw new Error('Failed to fetch promises');
      }

      const data = await response.json();
      setPromises(data.promises || []);
      // Initialize filtered promises with all promises
      setFilteredPromises(data.promises || []);
      
      // Extract unique ministers from reporting_lead_title field
      const uniqueMinisters: string[] = [];
      (data.promises || []).forEach((p: PromiseData) => {
        if (p.reporting_lead_title && !uniqueMinisters.includes(p.reporting_lead_title)) {
          uniqueMinisters.push(p.reporting_lead_title);
        }
      });
      uniqueMinisters.sort();
      setAvailableMinisters(['all', ...uniqueMinisters]);
    } catch (error) {
      console.error('Error fetching promises:', error);
      setError('Failed to load promises for selection');
    }
  };

  const searchEvidenceItems = async () => {
    if (!evidenceSearchText.trim()) {
      setEvidenceItems([]);
      setFilteredEvidenceItems([]);
      setEvidenceSearchPerformed(false);
      return;
    }

    setEvidenceLoading(true);
    try {
      // Search for evidence items
      const queryParams = new URLSearchParams();
      queryParams.append('parliament_session_id', currentSessionId!);
      queryParams.append('search', evidenceSearchText);
      queryParams.append('limit', '50');

      const response = await fetch(`/api/admin/evidence?${queryParams.toString()}`);
      if (!response.ok) {
        throw new Error('Failed to search evidence items');
      }

      const data = await response.json();
      setEvidenceItems(data.evidence_items || []);
      setFilteredEvidenceItems(data.evidence_items || []);
      setEvidenceSearchPerformed(true);
      
      // Debug logging to see the data structure
      if (data.evidence_items && data.evidence_items.length > 0) {
        console.log('Evidence items received:', data.evidence_items);
        console.log('First item structure:', data.evidence_items[0]);
        console.log('First item created_at:', data.evidence_items[0].created_at);
      }

      // Also fetch promises now that user is working with evidence
      if (promises.length === 0) {
        await fetchPromises();
      }
    } catch (error) {
      console.error('Error searching evidence items:', error);
      setError('Failed to search evidence items');
    } finally {
      setEvidenceLoading(false);
    }
  };

  const handleInputChange = (field: keyof EvidenceFormData, value: string) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
    setError(null);
  };

  const handlePromiseSelection = (promiseId: string, checked: boolean) => {
    setFormData(prev => ({
      ...prev,
      selected_promise_ids: checked 
        ? [...prev.selected_promise_ids, promiseId]
        : prev.selected_promise_ids.filter(id => id !== promiseId)
    }));
  };

  const handleEvidenceSelect = (evidenceItem: EvidenceItem) => {
    setSelectedEvidenceItem(evidenceItem);
    setFormData({
      source_url: evidenceItem.source_url,
      title_or_summary: evidenceItem.title_or_summary,
      description_or_details: evidenceItem.description_or_details,
      evidence_source_type: evidenceItem.evidence_source_type_key || evidenceItem.evidence_source_type || '',
      selected_promise_ids: evidenceItem.promise_ids || []
    });
    // Don't automatically switch to edit mode - let user decide
  };

  const handleEvidenceEdit = (evidenceItem: EvidenceItem) => {
    setSelectedEvidenceItem(evidenceItem);
    const promiseIds = evidenceItem.promise_ids || [];
    
    // Fix source type mapping: if we have the key, use it; otherwise reverse-map from label
    let sourceTypeKey = evidenceItem.evidence_source_type_key;
    if (!sourceTypeKey && evidenceItem.evidence_source_type) {
      sourceTypeKey = getSourceTypeKeyByLabel(evidenceItem.evidence_source_type);
    }
    
    setFormData({
      source_url: evidenceItem.source_url,
      title_or_summary: evidenceItem.title_or_summary,
      description_or_details: evidenceItem.description_or_details,
      evidence_source_type: sourceTypeKey || '',
      selected_promise_ids: promiseIds
    });
    setOriginalPromiseCount(promiseIds.length);
    setEvidenceMode('edit');
    setError(null);
    setSuccess(null);
  };

  const handleEvidenceDelete = async (evidenceItem: EvidenceItem) => {
    if (!confirm(`Are you sure you want to delete "${evidenceItem.title_or_summary}"?`)) {
      return;
    }
    
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/admin/evidence?id=${evidenceItem.id}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to delete evidence item');
      }

      setSuccess('Evidence item deleted successfully');
      
      // Refresh the search results
      if (evidenceSearchText.trim()) {
        await searchEvidenceItems();
      }

      // Clear selection if this was the selected item
      if (selectedEvidenceItem?.id === evidenceItem.id) {
        setSelectedEvidenceItem(null);
        handleCreateNew();
      }

    } catch (error) {
      console.error('Error deleting evidence:', error);
      setError(error instanceof Error ? error.message : 'Failed to delete evidence item');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateNew = () => {
    setSelectedEvidenceItem(null);
    setFormData({
      source_url: '',
      title_or_summary: '',
      description_or_details: '',
      evidence_source_type: '',
      selected_promise_ids: []
    });
    setOriginalPromiseCount(undefined);
    setEvidenceMode('create');
    setError(null);
    setSuccess(null);
  };

  const handleSearchDifferentItem = () => {
    setSelectedEvidenceItem(null);
    setFormData({
      source_url: '',
      title_or_summary: '',
      description_or_details: '',
      evidence_source_type: '',
      selected_promise_ids: []
    });
    setOriginalPromiseCount(undefined);
    setEvidenceSearchText('');  // Clear the search box
    setEvidenceItems([]);  // Clear search results
    setEvidenceSearchPerformed(false);  // Reset search state
    // Keep evidenceMode as 'edit' - don't change it
    setError(null);
    setSuccess(null);
  };

  const validateForm = (): boolean => {
    if (!formData.source_url.trim()) {
      setError('Source URL is required');
      return false;
    }

    if (creationMode === 'manual' || evidenceMode === 'edit') {
      if (!formData.title_or_summary.trim()) {
        setError('Title/Summary is required');
        return false;
      }
      if (!formData.description_or_details.trim()) {
        setError('Description/Details is required');
        return false;
      }
      if (!formData.evidence_source_type.trim()) {
        setError('Evidence Source Type is required');
        return false;
      }
    }

    return true;
  };

  const handleSubmit = async () => {
    if (!validateForm()) {
      return;
    }

    setIsLoading(true);
    setError(null);
    setSuccess(null);
    
    // Set initial loading message
    if (evidenceMode === 'edit' && selectedEvidenceItem) {
      setLoadingMessage('Updating evidence item...');
    } else if (creationMode === 'automated') {
      setLoadingMessage('Scraping page and LLM magic...');
    } else {
      setLoadingMessage('Creating evidence item...');
    }

    try {
      const payload = {
        creation_mode: creationMode,
        parliament_session_id: currentSessionId,
        selected_promise_ids: formData.selected_promise_ids,
        source_url: formData.source_url,
        title_or_summary: formData.title_or_summary,
        description_or_details: formData.description_or_details,
        evidence_source_type: formData.evidence_source_type
      };

      let response;
      
      if (evidenceMode === 'edit' && selectedEvidenceItem) {
        // Update existing evidence item
        response = await fetch(`/api/admin/evidence?id=${selectedEvidenceItem.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      } else {
        // Create new evidence item
        // For automated mode, show progressive status updates
        if (creationMode === 'automated') {
          // Set up progressive status updates for automated mode
          const statusUpdates = [
            { delay: 1000, message: 'Extracting webpage content...' },
            { delay: 3000, message: 'Analyzing content with AI...' },
            { delay: 6000, message: 'Generating structured evidence...' },
            { delay: 9000, message: 'Finalizing evidence item...' }
          ];

          statusUpdates.forEach(({ delay, message }) => {
            setTimeout(() => {
              if (isLoading) setLoadingMessage(message);
            }, delay);
          });
        }

        response = await fetch('/api/admin/evidence', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      }

      const result = await response.json();

      if (result.success) {
        if (evidenceMode === 'edit') {
          setSuccess(`Evidence item updated successfully! ID: ${result.evidence_id}`);
          // Update the selected evidence item with new data
          if (selectedEvidenceItem) {
            setSelectedEvidenceItem({
              ...selectedEvidenceItem,
              title_or_summary: formData.title_or_summary,
              description_or_details: formData.description_or_details,
              evidence_source_type: formData.evidence_source_type,
              source_url: formData.source_url,
              promise_ids: formData.selected_promise_ids
            });
            setOriginalPromiseCount(formData.selected_promise_ids.length);
          }
        } else {
          setSuccess(`Evidence item created successfully! ID: ${result.evidence_id}`);
          if (creationMode === 'automated' && result.analysis) {
            console.log('LLM Analysis completed:', result.analysis);
          }
          
          // If we have evidence data (both automated and manual), switch to edit mode
          if (result.evidence_data) {
            const evidenceData = result.evidence_data;
            console.log('Received evidence data:', evidenceData);
            console.log('Evidence source type key:', evidenceData.evidence_source_type_key);
            console.log('Evidence source type label:', evidenceData.evidence_source_type);
            
            const createdEvidenceItem: EvidenceItem = {
              id: result.evidence_id,
              title_or_summary: evidenceData.title_or_summary,
              description_or_details: evidenceData.description_or_details,
              evidence_source_type: evidenceData.evidence_source_type,
              source_url: evidenceData.source_url,
              promise_ids: evidenceData.promise_ids || [],
              created_at: evidenceData.ingested_at,
              promise_linking_status: evidenceData.promise_linking_status,
              linked_departments: evidenceData.linked_departments || []
            };
            
            // Load promises if they haven't been loaded yet
            if (promises.length === 0) {
              await fetchPromises();
            }
            
            // Switch to edit mode with the newly created evidence
            setSelectedEvidenceItem(createdEvidenceItem);
            const newFormData = {
              source_url: evidenceData.source_url,
              title_or_summary: evidenceData.title_or_summary,
              description_or_details: evidenceData.description_or_details,
              evidence_source_type: evidenceData.evidence_source_type_key || 'other',  // Use the key for the form
              selected_promise_ids: evidenceData.promise_ids || []
            };
            console.log('Setting form data:', newFormData);
            setFormData(newFormData);
            setOriginalPromiseCount(evidenceData.promise_ids?.length || 0);
            setEvidenceMode('edit');
            setEvidenceSearchPerformed(true); // Mark that evidence search has been performed
            
            // Update success message to indicate edit mode
            const modeText = creationMode === 'automated' ? 'automatically analyzed and created' : 'created';
            setSuccess(`Evidence item ${modeText} successfully! You can now review and modify the details or add promise links below. ID: ${result.evidence_id}`);
          } else {
            resetForm();
          }
        }
      } else {
        // Handle duplicate URL case
        if (result.duplicate && result.existing_item) {
          const existingItem = result.existing_item;
          const confirmEdit = confirm(
            `An evidence item with this URL already exists:\n\n` +
            `Title: ${existingItem.title_or_summary}\n` +
            `Created: ${formatDate(existingItem.created_at)}\n\n` +
            `Would you like to edit the existing item instead?`
          );
          
          if (confirmEdit) {
            // Load promises if they haven't been loaded yet
            if (promises.length === 0) {
              await fetchPromises();
            }
            
            // Switch to edit mode with the existing evidence item
            handleEvidenceEdit({
              id: existingItem.id,
              title_or_summary: existingItem.title_or_summary,
              description_or_details: existingItem.description_or_details,
              evidence_source_type: existingItem.evidence_source_type,
              evidence_source_type_key: existingItem.evidence_source_type_key,
              source_url: existingItem.source_url,
              promise_ids: existingItem.promise_ids || [],
              created_at: existingItem.created_at,
              promise_linking_status: existingItem.promise_linking_status,
              linked_departments: existingItem.linked_departments || []
            });
            setEvidenceSearchPerformed(true); // Mark that evidence search has been performed
            setSuccess(`Switched to editing existing evidence item: ${existingItem.title_or_summary}`);
          } else {
            setError(`An evidence item with this URL already exists. Please use a different URL or edit the existing item.`);
          }
        } else {
          setError(result.error || `Failed to ${evidenceMode === 'edit' ? 'update' : 'create'} evidence item`);
        }
      }
    } catch (error) {
      console.error(`Error ${evidenceMode === 'edit' ? 'updating' : 'creating'} evidence:`, error);
      setError(`Network error occurred while ${evidenceMode === 'edit' ? 'updating' : 'creating'} evidence`);
    } finally {
      setIsLoading(false);
      setLoadingMessage('');
    }
  };

  const formatDate = (date: any) => {
    if (!date) return 'N/A';
    try {
      // Handle Firestore Timestamp objects with _seconds and _nanoseconds
      if (date && typeof date === 'object' && (date._seconds || date.seconds)) {
        const seconds = date._seconds || date.seconds;
        const nanoseconds = date._nanoseconds || date.nanoseconds || 0;
        const d = new Date(seconds * 1000 + nanoseconds / 1000000);
        return d.toLocaleDateString();
      }
      // Handle regular Date objects or ISO strings
      const d = date.toDate ? date.toDate() : new Date(date);
      return d.toLocaleDateString();
    } catch (error) {
      console.error('Date formatting error:', error, 'for date:', date);
      return 'Invalid Date';
    }
  };

  // Helper for font class (matches main app)
  const fontClass = 'font-sans'; // soehne is set as default in tailwind.config.js or global.css

  const clearFilters = () => {
    setMinisterFilter('all');
    setRankFilter('all');
    setPromiseSearchText('');
  };
  const handleSearch = (selectedPromiseIds?: string[]) => {
    // Use passed parameter or current form data
    const promiseIdsToUse = selectedPromiseIds || formData.selected_promise_ids;
    
    // Apply promise search filter when button is clicked
    let filtered = [...promises];
    
    // Apply minister filter
    if (ministerFilter !== 'all') {
      filtered = filtered.filter(promise => promise.reporting_lead_title === ministerFilter);
    }
    
    // Apply rank filter
    if (rankFilter !== 'all') {
      if (rankFilter === 'none') {
        filtered = filtered.filter(promise => !promise.bc_promise_rank);
      } else {
        filtered = filtered.filter(promise => promise.bc_promise_rank === rankFilter);
      }
    }
    
    // Apply search filter across multiple fields
    if (promiseSearchText.trim()) {
      const searchLower = promiseSearchText.toLowerCase();
      filtered = filtered.filter(promise => 
        promise.text?.toLowerCase().includes(searchLower) ||
        promise.reporting_lead_title?.toLowerCase().includes(searchLower) ||
        promise.background_and_context?.toLowerCase().includes(searchLower)
      );
    }
    
    // Sort to move selected promises to the top
    if (promiseIdsToUse.length > 0) {
      filtered.sort((a, b) => {
        const aSelected = promiseIdsToUse.includes(a.id);
        const bSelected = promiseIdsToUse.includes(b.id);
        
        if (aSelected && !bSelected) return -1;
        if (!aSelected && bSelected) return 1;
        return 0;
      });
    }
    
    setFilteredPromises(filtered);
  };

  const handleSearchClick = () => {
    handleSearch();
  };

  // Reset form to initial state
  const resetForm = () => {
    setFormData({
      source_url: '',
      title_or_summary: '',
      description_or_details: '',
      evidence_source_type: '',
      selected_promise_ids: []
    });
  };

  // Memoize the expensive promises table to prevent re-rendering on unrelated state changes
  const memoizedPromisesTable = useMemo(() => {
    return (
      <div className="rounded-lg border bg-card text-card-foreground shadow-sm mt-4">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-12">Select</TableHead>
              <TableHead className="w-16">ID</TableHead>
              <TableHead className="w-96">Promise Description</TableHead>
              <TableHead>Source Type</TableHead>
              <TableHead>BC Rank</TableHead>
              <TableHead>BC Direction</TableHead>
              <TableHead>Department</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredPromises.map((promise) => (
              <TableRow 
                key={promise.id}
                className={
                  evidenceMode === 'edit' && formData.selected_promise_ids.includes(promise.id)
                    ? 'bg-blue-50 border-l-4 border-l-blue-400'
                    : ''
                }
              >
                <TableCell>
                  <Checkbox
                    checked={formData.selected_promise_ids.includes(promise.id)}
                    onCheckedChange={(checked) => handlePromiseSelection(promise.id, checked as boolean)}
                    className="white-checkmark"
                  />
                </TableCell>
                <TableCell className="font-medium text-xs break-words">{promise.id}</TableCell>
                <TableCell className="text-xs w-96" title={promise.text}>
                  {promise.text}
                </TableCell>
                <TableCell className="text-xs">{promise.source_type}</TableCell>
                <TableCell className="text-xs">{promise.bc_promise_rank}</TableCell>
                <TableCell className="text-xs">{promise.bc_promise_direction}</TableCell>
                <TableCell className="text-xs">{promise.responsible_department_lead || 'N/A'}</TableCell>
                <TableCell className="text-xs">{promise.status === 'deleted' ? 'Deleted' : 'Active'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {filteredPromises.length === 0 && (
          <div className="p-8 text-center text-gray-500">
            {promiseSearchText ? 'No promises match your search' : 'No promises available'}
          </div>
        )}
      </div>
    );
  }, [filteredPromises, evidenceMode, formData.selected_promise_ids, promiseSearchText]);

  if (isLoadingSessions) {
    return <div className="min-h-screen bg-gray-50 p-8">Loading session information...</div>;
  }

  if (!currentSessionId) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            No active parliamentary session found. Please configure the session in settings.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className={clsx('min-h-screen', fontClass)}>
      {/* Header */}
      <div className="bg-white border-b p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div>
              <h1 className={clsx('text-2xl font-bold text-gray-900', fontClass)}>Manage Evidence</h1>
              <p className={clsx('text-sm text-gray-600', fontClass)}>Create, edit, and link evidence items to promises</p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            {evidenceMode === 'edit' && selectedEvidenceItem && (
              <Badge variant="outline" className={clsx('text-xs', fontClass)}>
                {formData.selected_promise_ids.length} promise{formData.selected_promise_ids.length !== 1 ? 's' : ''} selected
                {originalPromiseCount !== undefined && originalPromiseCount !== formData.selected_promise_ids.length && (
                  <span className="ml-1 font-bold text-orange-600">
                    ({formData.selected_promise_ids.length > originalPromiseCount ? '+' : ''}{formData.selected_promise_ids.length - originalPromiseCount})
                  </span>
                )}
              </Badge>
            )}
            {selectedEvidenceItem && (
              <Badge className={clsx('bg-blue-100 text-blue-800 text-xs', fontClass)}>
                Selected: {selectedEvidenceItem.title_or_summary.substring(0, 30)}...
              </Badge>
            )}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="p-6 space-y-8">
        {/* Alerts */}
        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription className={fontClass}>{error}</AlertDescription>
          </Alert>
        )}

        {success && (
          <Alert className="border-green-200 bg-green-50">
            <AlertDescription className={clsx('text-green-800', fontClass)}>{success}</AlertDescription>
          </Alert>
        )}

        {/* Evidence Management Panel */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className={clsx('flex items-center space-x-2', fontClass)}>
                  {evidenceMode === 'create' ? <Plus className="h-5 w-5" /> : <SquarePen className="h-5 w-5" />}
                  <span>{evidenceMode === 'create' ? 'Create Evidence Item' : 'Edit Evidence Item'}</span>
                </CardTitle>
                <CardDescription className={fontClass}>
                  {evidenceMode === 'create'
                    ? 'Add new evidence manually or automatically from a URL'
                    : 'Update existing evidence item details and promise links'}
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <Tabs value={evidenceMode} onValueChange={(value) => setEvidenceMode(value as 'create' | 'edit')}>
              <TabsList className="grid w-full grid-cols-2 max-w-md">
                <TabsTrigger
                  value="edit"
                  className={clsx(
                    'transition-all duration-200',
                    fontClass,
                    evidenceMode === 'edit' && 'bg-[#8b2332] text-white border border-[#8b2332] shadow',
                    evidenceMode !== 'edit' && 'bg-[#f6ebe3] text-[#0a0a0a]'
                  )}
                >
                  EDIT EXISTING
                </TabsTrigger>
                <TabsTrigger
                  value="create"
                  className={clsx(
                    'transition-all duration-200',
                    fontClass,
                    evidenceMode === 'create' && 'bg-[#8b2332] text-white border border-[#8b2332] shadow',
                    evidenceMode !== 'create' && 'bg-[#f6ebe3] text-[#0a0a0a]'
                  )}
                >
                  CREATE NEW
                </TabsTrigger>
              </TabsList>

              <TabsContent value="create" className="space-y-6 mt-6">
                <Tabs value={creationMode} onValueChange={(value) => setCreationMode(value as 'automated' | 'manual')}>
                  <TabsList className="grid w-full grid-cols-2 max-w-md">
                    <TabsTrigger
                      value="automated"
                      className={clsx(
                        'transition-all duration-200',
                        fontClass,
                        creationMode === 'automated' && 'bg-[#8b2332] text-white border border-[#8b2332] shadow',
                        creationMode !== 'automated' && 'bg-[#f6ebe3] text-[#0a0a0a]'
                      )}
                    >
                      AUTOMATED CREATE
                    </TabsTrigger>
                    <TabsTrigger
                      value="manual"
                      className={clsx(
                        'transition-all duration-200',
                        fontClass,
                        creationMode === 'manual' && 'bg-[#8b2332] text-white border border-[#8b2332] shadow',
                        creationMode !== 'manual' && 'bg-[#f6ebe3] text-[#0a0a0a]'
                      )}
                    >
                      MANUAL CREATE
                    </TabsTrigger>
                  </TabsList>

                  <TabsContent value="automated" className="space-y-6 mt-6">
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                      <div className="flex items-start space-x-3">
                        <Link className="h-5 w-5 text-blue-600 mt-0.5" />
                        <div>
                          <h4 className="text-sm font-medium text-blue-900">Automated Content Extraction</h4>
                          <p className="text-sm text-blue-700 mt-1">
                            Provide a URL and we'll automatically extract the title, description, publication date, and other relevant details from the webpage.
                          </p>
                        </div>
                      </div>
                    </div>
                    
                    <div className="space-y-4">
                      <div>
                        <Label htmlFor="source_url_auto" className="text-sm font-medium">Source URL *</Label>
                        <Input
                          id="source_url_auto"
                          type="url"
                          placeholder="https://example.com/news-article-or-document"
                          value={formData.source_url}
                          onChange={(e) => handleInputChange('source_url', e.target.value)}
                          className="mt-1"
                        />
                        <p className="text-xs text-gray-500 mt-1">
                          Enter the URL of the news article, government announcement, or document you want to add as evidence.
                        </p>
                      </div>
                    </div>

                    <div className="flex justify-end pt-4">
                      <Button 
                        onClick={handleSubmit}
                        disabled={isLoading}
                        className="flex items-center space-x-2 bg-[#8b2332] text-white hover:bg-[#721c28] font-bold px-6 py-2 rounded shadow disabled:opacity-50"
                      >
                        <Plus className="h-4 w-4" />
                        <span>
                          {isLoading ? (
                            loadingMessage || 'Processing...'
                          ) : (
                            'Create Evidence'
                          )}
                        </span>
                      </Button>
                    </div>
                  </TabsContent>

                  <TabsContent value="manual" className="space-y-6 mt-6">
                    <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                      <div className="flex items-start space-x-3">
                        <SquarePen className="h-5 w-5 text-amber-600 mt-0.5" />
                        <div>
                          <h4 className="text-sm font-medium text-amber-900">Manual Entry</h4>
                          <p className="text-sm text-amber-700 mt-1">
                            Manually provide all evidence details. Use this when automatic extraction isn't suitable or when you need precise control over the content.
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-4">
                        <div>
                          <Label htmlFor="source_url_manual" className="text-sm font-medium">Source URL *</Label>
                          <Input
                            id="source_url_manual"
                            type="url"
                            placeholder="https://example.com/source"
                            value={formData.source_url}
                            onChange={(e) => handleInputChange('source_url', e.target.value)}
                            className="mt-1"
                          />
                        </div>

                        <div>
                          <Label htmlFor="evidence_source_type_manual" className="text-sm font-medium">Source Type *</Label>
                          <Select value={formData.evidence_source_type} onValueChange={(value) => handleInputChange('evidence_source_type', value)}>
                            <SelectTrigger className="mt-1">
                              <SelectValue placeholder="Select evidence source type" />
                            </SelectTrigger>
                            <SelectContent>
                              {EVIDENCE_SOURCE_TYPES.map((type) => (
                                <SelectItem key={type.value} value={type.value}>
                                  {type.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      </div>

                      <div className="space-y-4">
                        <div>
                          <Label htmlFor="title_manual" className="text-sm font-medium">Title/Summary *</Label>
                          <Input
                            id="title_manual"
                            placeholder="Brief, descriptive title for this evidence"
                            value={formData.title_or_summary}
                            onChange={(e) => handleInputChange('title_or_summary', e.target.value)}
                            className="mt-1"
                          />
                        </div>

                        <div>
                          <Label htmlFor="description_manual" className="text-sm font-medium">Description/Details *</Label>
                          <Textarea
                            id="description_manual"
                            placeholder="Detailed description of the evidence and how it relates to government promises"
                            value={formData.description_or_details}
                            onChange={(e) => handleInputChange('description_or_details', e.target.value)}
                            rows={4}
                            className="mt-1"
                          />
                        </div>
                      </div>
                    </div>

                    <div className="flex justify-end pt-4">
                      <Button 
                        onClick={handleSubmit}
                        disabled={isLoading}
                        className="flex items-center space-x-2 bg-[#8b2332] text-white hover:bg-[#721c28] font-bold px-6 py-2 rounded shadow disabled:opacity-50"
                      >
                        <Plus className="h-4 w-4" />
                        <span>
                          {isLoading ? (
                            loadingMessage || 'Processing...'
                          ) : (
                            'Create Evidence'
                          )}
                        </span>
                      </Button>
                    </div>
                  </TabsContent>
                </Tabs>
              </TabsContent>

              <TabsContent value="edit" className="space-y-6 mt-6">
                {!selectedEvidenceItem ? (
                  <div className="space-y-6">
                    <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                      <div className="flex items-start space-x-3">
                        <Search className="h-5 w-5 text-gray-600 mt-0.5" />
                        <div>
                          <h4 className="text-sm font-medium text-gray-900">Find Evidence to Edit</h4>
                          <p className="text-sm text-gray-600 mt-1">
                            Search for existing evidence items by title, description, or source URL. Select an item to edit its details and promise links.
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="space-y-4">
                      <div className="flex space-x-2">
                        <div className="flex-1">
                          <Input
                            placeholder="Search evidence items by title, description, or URL..."
                            value={evidenceSearchText}
                            onChange={(e) => setEvidenceSearchText(e.target.value)}
                            onKeyPress={(e) => e.key === 'Enter' && searchEvidenceItems()}
                          />
                        </div>
                        <Button 
                          onClick={searchEvidenceItems}
                          disabled={evidenceLoading || !evidenceSearchText.trim()}
                          className="bg-[#8b2332] hover:bg-[#721c28] text-white"
                        >
                          <Search className="h-4 w-4 mr-2" />
                          {evidenceLoading ? 'Searching...' : 'Search'}
                        </Button>
                      </div>

                      {evidenceSearchPerformed && (
                        <div className="border rounded-lg overflow-hidden">
                          <Table>
                            <TableHeader>
                              <TableRow>
                                <TableHead>Title</TableHead>
                                <TableHead>Source Type</TableHead>
                                <TableHead>Evidence Date</TableHead>
                                <TableHead>Promises</TableHead>
                                <TableHead className="w-32">Actions</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {filteredEvidenceItems.map((item) => (
                                <TableRow 
                                  key={item.id}
                                  className="cursor-pointer hover:bg-gray-50"
                                  onClick={() => handleEvidenceEdit(item)}
                                >
                                  <TableCell>
                                    <div className="max-w-md">
                                      <p className="font-medium text-sm">{item.title_or_summary}</p>
                                      <p className="text-xs text-gray-500 mt-1 truncate">
                                        {item.description_or_details}
                                      </p>
                                    </div>
                                  </TableCell>
                                  <TableCell>
                                    <Badge variant="outline" className="text-xs">
                                      {getSourceTypeKeyByLabel(item.evidence_source_type)}
                                    </Badge>
                                  </TableCell>
                                  <TableCell className="text-sm">
                                    {formatDate(item.evidence_date)}
                                  </TableCell>
                                  <TableCell className="text-sm">
                                    {item.promise_ids?.length || 0} linked
                                  </TableCell>
                                  <TableCell onClick={(e) => e.stopPropagation()}>
                                    <div className="flex space-x-1">
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        onClick={() => handleEvidenceEdit(item)}
                                        className="h-8 w-8 p-0"
                                        title="Edit Evidence"
                                      >
                                        <SquarePen className="h-3.5 w-3.5" />
                                      </Button>
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        onClick={() => window.open(item.source_url, '_blank')}
                                        className="h-8 w-8 p-0"
                                        title="Open Source URL"
                                      >
                                        <Link className="h-3 w-3" />
                                      </Button>
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        onClick={() => handleEvidenceDelete(item)}
                                        className="h-8 w-8 p-0 hover:bg-red-50 hover:border-red-200"
                                        title="Delete Evidence"
                                      >
                                        <Trash2 className="h-3.5 w-3.5 text-red-600" />
                                      </Button>
                                    </div>
                                  </TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                          
                          {filteredEvidenceItems.length === 0 && (
                            <div className="p-8 text-center text-gray-500">
                              {evidenceSearchText ? 'No evidence items match your search' : 'Enter a search term to find evidence items'}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="space-y-6">
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <h4 className="text-sm font-medium text-blue-900">Editing Evidence Item</h4>
                          <p className="text-sm text-blue-700 mt-1">
                            {selectedEvidenceItem.title_or_summary}
                          </p>
                        </div>
                        <Button variant="outline" size="sm" onClick={handleSearchDifferentItem}>
                          <Search className="h-4 w-4 mr-2" />
                          Search Different Item
                        </Button>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-4">
                        <div>
                          <Label htmlFor="edit_source_url" className="text-sm font-medium">Source URL *</Label>
                          <Input
                            id="edit_source_url"
                            type="url"
                            value={formData.source_url}
                            onChange={(e) => handleInputChange('source_url', e.target.value)}
                            className="mt-1"
                          />
                        </div>

                        <div>
                          <Label htmlFor="edit_evidence_source_type" className="text-sm font-medium">Source Type *</Label>
                          <Select value={formData.evidence_source_type} onValueChange={(value) => handleInputChange('evidence_source_type', value)}>
                            <SelectTrigger className="mt-1">
                              <SelectValue placeholder="Select evidence source type" />
                            </SelectTrigger>
                            <SelectContent>
                              {EVIDENCE_SOURCE_TYPES.map((type) => (
                                <SelectItem key={type.value} value={type.value}>
                                  {type.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      </div>

                      <div className="space-y-4">
                        <div>
                          <Label htmlFor="edit_title" className="text-sm font-medium">Title/Summary *</Label>
                          <Input
                            id="edit_title"
                            value={formData.title_or_summary}
                            onChange={(e) => handleInputChange('title_or_summary', e.target.value)}
                            className="mt-1"
                          />
                        </div>

                        <div>
                          <Label htmlFor="edit_description" className="text-sm font-medium">Description/Details *</Label>
                          <Textarea
                            id="edit_description"
                            value={formData.description_or_details}
                            onChange={(e) => handleInputChange('description_or_details', e.target.value)}
                            rows={4}
                            className="mt-1"
                          />
                        </div>
                      </div>
                    </div>

                    <div className="flex space-x-3 pt-4">
                      <Button 
                        onClick={handleSubmit}
                        disabled={isLoading}
                        className="flex items-center space-x-2 bg-[#8b2332] hover:bg-[#721c28] text-white"
                      >
                        <SquarePen className="h-4 w-4" />
                        <span>{isLoading ? 'Updating...' : 'Update Evidence'}</span>
                      </Button>
                      <Button 
                        variant="outline" 
                        onClick={handleCreateNew}
                        className="flex items-center space-x-2"
                      >
                        <RotateCcw className="h-4 w-4" />
                        <span>Cancel</span>
                      </Button>
                    </div>
                  </div>
                )}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        {/* Promise Linking Panel - Only show when editing a specific evidence item */}
        {evidenceMode === 'edit' && selectedEvidenceItem && (
          <Card className="ring-2 ring-blue-200 border-blue-300">
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Link className="h-5 w-5" />
                <span>Link to Promises</span>
                <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
                  Editing Links
                </Badge>
              </CardTitle>
              <CardDescription>
                <div className="space-y-1">
                  <p>Modify which promises this evidence relates to. Check/uncheck boxes to add or remove promise links.</p>
                  <p className="text-sm font-medium text-blue-600">
                    Currently linked to {formData.selected_promise_ids.length} promise{formData.selected_promise_ids.length !== 1 ? 's' : ''}
                    {originalPromiseCount !== undefined && originalPromiseCount !== formData.selected_promise_ids.length && (
                      <span className="ml-2 text-orange-600">
                        ({formData.selected_promise_ids.length > originalPromiseCount ? '+' : ''}{formData.selected_promise_ids.length - originalPromiseCount} change{Math.abs(formData.selected_promise_ids.length - originalPromiseCount) !== 1 ? 's' : ''})
                      </span>
                    )}
                  </p>
                </div>
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="rounded-lg border bg-card text-card-foreground shadow-sm p-6 space-y-4">
                <h2 className="text-xl font-semibold flex items-center">
                  <Search className="mr-2 h-5 w-5" />
                  Filters & Search
                  <span className="ml-4 text-sm font-normal text-gray-600">
                    (Parliament Session: {currentSessionId})
                  </span>
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <Select value={ministerFilter} onValueChange={setMinisterFilter}>
                    <SelectTrigger><SelectValue placeholder="Minister" /></SelectTrigger>
                    <SelectContent>
                      {availableMinisters.map(minister => (
                        <SelectItem key={minister} value={minister}>
                          {minister === 'all' ? 'All Ministers' : minister}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Select value={rankFilter} onValueChange={setRankFilter}>
                    <SelectTrigger><SelectValue placeholder="BC Promise Rank" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Ranks</SelectItem>
                      <SelectItem value="strong">Strong</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="weak">Weak</SelectItem>
                      <SelectItem value="none">Not Ranked</SelectItem>
                    </SelectContent>
                  </Select>
                  <Input
                    type="text"
                    placeholder="Search in text, minister, or background..."
                    value={promiseSearchText}
                    onChange={(e) => setPromiseSearchText(e.target.value)}
                    className="md:col-span-1"
                  />
                </div>
                <div className="flex justify-end space-x-2">
                  <Button onClick={handleSearchClick} className="flex items-center bg-[#8b2332] hover:bg-[#721c28] text-white">
                    <Search className="mr-2 h-4 w-4" /> Apply Filters
                  </Button>
                </div>
              </div>
              {memoizedPromisesTable}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
} 