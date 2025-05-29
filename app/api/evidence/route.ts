import { NextRequest, NextResponse } from 'next/server';
import { fetchEvidenceItemsByIds } from '@/lib/data';

export async function POST(request: NextRequest) {
  try {
    const { evidenceIds, sessionsStartDate, sessionEndDate } = await request.json();

    if (!evidenceIds || !Array.isArray(evidenceIds)) {
      return NextResponse.json({ error: 'Invalid evidenceIds' }, { status: 400 });
    }

    const evidenceItems = await fetchEvidenceItemsByIds(
      evidenceIds,
      sessionsStartDate || null,
      sessionEndDate || null
    );

    return NextResponse.json({ evidenceItems }, { status: 200 });
  } catch (error) {
    console.error('[Evidence API] Error fetching evidence items:', error);
    return NextResponse.json({ error: 'Failed to fetch evidence items' }, { status: 500 });
  }
} 