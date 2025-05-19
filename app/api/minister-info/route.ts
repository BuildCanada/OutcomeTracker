import { NextResponse } from 'next/server';
import { firestoreAdmin } from "@/lib/firebaseAdmin";
import { fetchMinisterForDepartmentInSessionAdmin } from "@/lib/server-utils";
import type { DepartmentConfig, ParliamentSession } from "@/lib/types";
import { Timestamp } from 'firebase-admin/firestore';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const departmentId = searchParams.get('departmentId');
  const sessionId = searchParams.get('sessionId'); // This is the parliament_number string

  if (!departmentId || !sessionId) {
    return NextResponse.json({ error: 'Missing departmentId or sessionId' }, { status: 400 });
  }

  console.log(`[API /minister-info] Received request for Dept ID: ${departmentId}, Session (Parl No.): ${sessionId}`);

  try {
    // 1. Fetch DepartmentConfig
    const deptConfigDoc = await firestoreAdmin.collection('department_config').doc(departmentId).get();
    if (!deptConfigDoc.exists) {
      console.error(`[API /minister-info] DepartmentConfig not found for ID: ${departmentId}`);
      return NextResponse.json({ error: 'Department configuration not found' }, { status: 404 });
    }
    // Serialize DepartmentConfig timestamps if any (similar to how page.tsx does it)
    const deptConfigData = deptConfigDoc.data() as any; // Cast to any to allow iterating keys
    const serializedDeptConfig: { [key: string]: any } = {};
    for (const key in deptConfigData) {
      if (deptConfigData[key] instanceof Timestamp) {
        serializedDeptConfig[key] = (deptConfigData[key] as Timestamp).toDate().toISOString();
      } else {
        serializedDeptConfig[key] = deptConfigData[key];
      }
    }
    const departmentConfig = { id: deptConfigDoc.id, ...serializedDeptConfig } as DepartmentConfig;
    console.log(`[API /minister-info] Fetched DepartmentConfig for ID: ${departmentId}`);

    // 2. Fetch ParliamentSession
    const sessionDoc = await firestoreAdmin.collection('parliament_session').doc(sessionId).get(); // sessionId is the parliament_number
    if (!sessionDoc.exists) {
      console.error(`[API /minister-info] ParliamentSession not found for ID (Parl No.): ${sessionId}`);
      return NextResponse.json({ error: 'Parliament session not found' }, { status: 404 });
    }
    // Serialize ParliamentSession timestamps (similar to how page.tsx does it)
    const sessionDataRaw = sessionDoc.data() as any; // Cast to any
    const serializedSessionData: { [key: string]: any } = {};
     for (const key of ['start_date', 'end_date', 'election_date_preceding', 'election_called_date']) {
      if (sessionDataRaw[key] instanceof Timestamp) {
        serializedSessionData[key] = (sessionDataRaw[key] as Timestamp).toDate().toISOString();
      } else if (sessionDataRaw[key]) { // Copy other defined date fields if they are already strings
        serializedSessionData[key] = sessionDataRaw[key];
      }
    }
    // Merge other fields from sessionDataRaw
    Object.keys(sessionDataRaw).forEach(key => {
        if (!serializedSessionData.hasOwnProperty(key)) {
            serializedSessionData[key] = sessionDataRaw[key];
        }
    });

    const parliamentSession = { 
        id: sessionDoc.id, 
        ...serializedSessionData,
        parliament_number: sessionDataRaw.parliament_number || sessionId // Ensure parliament_number is present
    } as ParliamentSession;
    console.log(`[API /minister-info] Fetched ParliamentSession for ID (Parl No.): ${sessionId}`);


    // 3. Call the utility function
    const ministerInfo = await fetchMinisterForDepartmentInSessionAdmin(departmentConfig, parliamentSession);

    if (!ministerInfo) {
      console.log(`[API /minister-info] No minister info found by fetchMinisterForDepartmentInSessionAdmin for Dept: ${departmentId}, Session: ${sessionId}`);
      // Return null or an empty object based on how client expects it for "Not Available"
      return NextResponse.json(null, { status: 200 }); // Or status 404 if that's more appropriate for client
    }

    console.log(`[API /minister-info] Successfully fetched minister info for Dept: ${departmentId}, Session: ${sessionId}`);
    return NextResponse.json(ministerInfo, { status: 200 });

  } catch (error) {
    console.error(`[API /minister-info] Error fetching minister info for Dept: ${departmentId}, Session: ${sessionId}:`, error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
} 