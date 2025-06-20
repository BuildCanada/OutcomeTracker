import { NextRequest, NextResponse } from 'next/server';

const READ_ONLY_FIELDS = [
  'id',
  'region_code',
  'party_code',
  'migration_metadata',
  'ingested_at',
  'explanation_enriched_at',
  'linking_preprocessing_done_at',
];

// === PUT: Update a promise ===
export async function PUT(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const { id } = params;
  if (!id) {
    return NextResponse.json({ error: 'Promise ID is required' }, { status: 400 });
  }

  try {
    const body = await request.json();

    // Clean and prepare payload
    const cleanedPayload: Record<string, any> = {};
    for (const [key, value] of Object.entries(body)) {
      if (READ_ONLY_FIELDS.includes(key)) continue;

      if (
        ['bc_promise_rank', 'bc_promise_direction', 'bc_promise_rank_rationale'].includes(key) &&
        value === ''
      ) {
        cleanedPayload[key] = null;
      } else if (value !== undefined) {
        cleanedPayload[key] = value;
      }
    }

    console.log(`🔄 Updating promise ${id} with:`, cleanedPayload);

    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/admin/promises/${id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(cleanedPayload),
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({ error: 'Unknown error' }));
      console.error(`❌ API error from Rails:`, error);
      return NextResponse.json(error, { status: res.status });
    }

    const json = await res.json();
    return NextResponse.json(json, { status: 200 });
  } catch (error: any) {
    console.error(`🚨 Failed to update promise ${id}:`, error);
    return NextResponse.json(
      { error: 'Failed to update promise.', details: error.message || 'Unknown error' },
      { status: 500 }
    );
  }
}

// === DELETE: Soft delete a promise ===
export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const { id } = params;
  if (!id) {
    return NextResponse.json({ error: 'Promise ID is required' }, { status: 400 });
  }

  try {
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/admin/promises/${id}`, {
      method: 'DELETE',
      headers: {
        Accept: 'application/json',
      },
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({ error: 'Unknown error' }));
      return NextResponse.json(error, { status: res.status });
    }

    const json = await res.json();
    return NextResponse.json(json, { status: 200 });
  } catch (error: any) {
    console.error(`❌ Error deleting promise ${id}:`, error);
    return NextResponse.json(
      { error: 'Failed to delete promise.', details: error.message || 'Unknown error' },
      { status: 500 }
    );
  }
}
