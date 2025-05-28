import { NextRequest, NextResponse } from 'next/server';
import { fetchEvidenceItemsByIds } from '@/lib/data';

export async function POST(request: NextRequest) {
  try {
    const { evidenceIds, sessionStartDate, sessionEndDate } = await request.json();
    
    if (!evidenceIds || !Array.isArray(evidenceIds)) {
      return NextResponse.json(
        { error: 'evidenceIds array is required' },
        { status: 400 }
      );
    }

    const evidenceItems = await fetchEvidenceItemsByIds(
      evidenceIds,
      sessionStartDate || null,
      sessionEndDate || null
    );

    return NextResponse.json({
      evidenceItems,
      count: evidenceItems.length
    });
  } catch (error) {
    console.error('Error fetching evidence items:', error);
    return NextResponse.json(
      { error: 'Failed to fetch evidence items' },
      { status: 500 }
    );
  }
} 