import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);

  const params = new URLSearchParams();

  // Carry over query params from the request
  ['source_type', 'bc_promise_rank', 'parliament_session_id', 'searchText', 'limit', 'page'].forEach(key => {
    const value = searchParams.get(key);
    if (value) params.append(key, value);
  });

  try {
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/admin/promises?${params.toString()}`, {
      headers: {
        Accept: 'application/json',
      },
    });

    if (!res.ok) {
      const errorText = await res.text();
      return NextResponse.json({ error: 'API error', details: errorText }, { status: res.status });
    }

    const json = await res.json();

    return NextResponse.json(
      {
        promises: json.data ?? [],
        total: json.meta?.total ?? (json.data?.length || 0),
      },
      { status: 200 }
    );
  } catch (error) {
    console.error('Error connecting to Rails API:', error);
    return NextResponse.json({ error: 'Failed to fetch from backend API' }, { status: 500 });
  }
}
