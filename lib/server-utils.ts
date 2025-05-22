import { firestoreAdmin } from "@/lib/firebaseAdmin";
import type { MinisterInfo, DepartmentConfig, ParliamentSession } from "@/lib/types";

// Default placeholder avatar, moved from page.tsx
const DEFAULT_PLACEHOLDER_AVATAR = "/placeholder.svg?height=100&width=100";

// Function to fetch minister details 
export async function fetchMinisterForDepartmentInSessionAdmin(
  departmentConfig: DepartmentConfig,
  session: ParliamentSession
): Promise<MinisterInfo | null> {
  console.log(`[Server Utils Info] Fetching minister for department: ${departmentConfig.official_full_name || departmentConfig.id} (Session ID: ${session.id}, Parl No: ${session.parliament_number}) using 'department_ministers' collection.`);
  if (!firestoreAdmin) {
    console.error(`[Server Utils Error] Firestore admin not available for dept: ${departmentConfig.id}`);
    return null;
  }
  if (!session || !session.parliament_number || !session.start_date) {
    console.error(`[Server Utils Error] Session info (parliament_number, start_date) missing for dept: ${departmentConfig.id}`, session);
    return null;
  }

  let departmentIdForQuery = departmentConfig.id;
  let effectiveDeptConfigForName = departmentConfig; // Store the config to use for the final name
  // const parliamentNumberStr = String(session.parliament_number); // We'll use session.id for mapping key

  // Check for historical mapping using session.id as the key (e.g., "44-1")
  const historicalMapping = departmentConfig.historical_mapping?.[session.id];

  if (historicalMapping && historicalMapping.minister_lookup_slug) {
    console.log(`[Server Utils Info] Applying historical mapping for Dept ID: '${departmentConfig.id}' in Session ID: '${session.id}'. Using historical minister_lookup_slug: '${historicalMapping.minister_lookup_slug}'.`);
    departmentIdForQuery = historicalMapping.minister_lookup_slug;

    // Attempt to fetch the historical department config for its name, using the minister_lookup_slug as its ID
    try {
      const historicalDeptDoc = await firestoreAdmin.collection('department_config').doc(historicalMapping.minister_lookup_slug).get();
      if (historicalDeptDoc.exists) {
        effectiveDeptConfigForName = historicalDeptDoc.data() as DepartmentConfig;
        effectiveDeptConfigForName.id = historicalDeptDoc.id; // Ensure ID is part of the object
        console.log(`[Server Utils Info] Successfully fetched historical DepartmentConfig for '${historicalMapping.minister_lookup_slug}' to use its name: ${effectiveDeptConfigForName.official_full_name}`);
      } else {
        console.warn(`[Server Utils Warn] Historical DepartmentConfig not found for ID: '${historicalMapping.minister_lookup_slug}'. Will use original department name for display if minister is found.`);
      }
    } catch (configError) {
      console.error(`[Server Utils Error] Error fetching historical DepartmentConfig for '${historicalMapping.minister_lookup_slug}':`, configError);
      // Continue with original departmentConfig for name if historical fetch fails
    }
  } else {
    // Ensure parliamentNumberStr is defined if not using historical mapping for other parts of the function
    // const parliamentNumberStr = String(session.parliament_number);
  }
  // We still need parliamentNumberStr for the Firestore query regardless of mapping
  const parliamentNumberStr = String(session.parliament_number);

  let t0 = Date.now();
  try {
    const ministersQuerySnapshot = await firestoreAdmin
      .collection('department_ministers')
      .where('departmentId', '==', departmentIdForQuery) // Use the potentially remapped ID
      .where('parliamentNumber', '==', parliamentNumberStr) // Use the string version of parliament number
      .get();

    console.log(`[Server Utils LCP Timing] Query to 'department_ministers' for dept ${departmentIdForQuery} (parl ${parliamentNumberStr}) took ${Date.now() - t0} ms. Found ${ministersQuerySnapshot.docs.length} potential records.`);

    if (ministersQuerySnapshot.empty) {
      console.log(`[Server Utils Info] No minister records found in 'department_ministers' for Dept ID: ${departmentIdForQuery}, Parliament: ${parliamentNumberStr}.`);
      return null;
    }

    interface CandidateMinisterEntry {
      docId: string;
      name: string;
      firstName: string;
      lastName: string;
      party: string;
      title: string;
      avatarUrl?: string;
      positionStart: Date;
      positionEnd?: Date;
    }

    const mappedRecords: (CandidateMinisterEntry | null)[] = ministersQuerySnapshot.docs.map(doc => {
      const ministerData = doc.data();
      if (!ministerData) return null;
      try {
        const posStartDateStr = ministerData.positionStart;
        const posEndDateStr = ministerData.positionEnd;
        if (!posStartDateStr || typeof posStartDateStr !== 'string') {
          console.warn(`[Server Utils Warn] Minister record ${doc.id} for dept ${departmentIdForQuery} missing or invalid positionStart.`);
          return null;
        }
        const posStartDate = new Date(posStartDateStr);
        const posEndDate = posEndDateStr && typeof posEndDateStr === 'string' ? new Date(posEndDateStr) : null;

        if (isNaN(posStartDate.getTime()) || (posEndDate && isNaN(posEndDate.getTime()))) {
          console.warn(`[Server Utils Warn] Minister record ${doc.id} for dept ${departmentIdForQuery} has invalid date strings.`);
          return null;
        }
        
        return {
          docId: doc.id,
          name: ministerData.fullName || `${ministerData.firstName || ''} ${ministerData.lastName || ''}`.trim() || 'Name Missing',
          firstName: ministerData.firstName || '',
          lastName: ministerData.lastName || '',
          party: ministerData.party || '',
          title: ministerData.title || 'Title Missing',
          avatarUrl: ministerData.avatarUrl,
          positionStart: posStartDate,
          positionEnd: posEndDate || undefined,
        };
      } catch (e) {
        console.error(`[Server Utils Error] Error processing minister record ${doc.id} for dept ${departmentIdForQuery}:`, e);
        return null;
      }
    });

    const allMinisterRecords: CandidateMinisterEntry[] = mappedRecords.filter((m): m is CandidateMinisterEntry => m !== null);


    let effectiveMinisterQueryDate = new Date(session.start_date);
    let candidates: CandidateMinisterEntry[] = allMinisterRecords.filter(m => {
      const startsOnOrBeforeQueryDate = m.positionStart <= effectiveMinisterQueryDate;
      const endsOnOrAfterQueryDate = m.positionEnd ? m.positionEnd >= effectiveMinisterQueryDate : true; // Active if no end date
      return startsOnOrBeforeQueryDate && endsOnOrAfterQueryDate;
    });

    if (candidates.length === 0 && session.election_date_preceding) {
      const electionDate = new Date(session.election_date_preceding);
      if (!isNaN(electionDate.getTime())) {
        console.log(`[Server Utils Info] No minister found for Dept ${departmentIdForQuery} using session_start_date (${session.start_date}). Trying election_date_preceding (${session.election_date_preceding}).`);
        effectiveMinisterQueryDate = electionDate;
        candidates = allMinisterRecords.filter(m => {
          const startsOnOrBeforeQueryDate = m.positionStart <= effectiveMinisterQueryDate;
          const endsOnOrAfterQueryDate = m.positionEnd ? m.positionEnd >= effectiveMinisterQueryDate : true; // Active if no end date
          return startsOnOrBeforeQueryDate && endsOnOrAfterQueryDate;
        });
      } else {
        console.warn(`[Server Utils Warn] session.election_date_preceding ('${session.election_date_preceding}') is invalid for session ${session.id}.`);
      }
    }

    if (candidates.length === 0) {
      console.log(`[Server Utils Info] No *active* minister found for Dept: ${departmentConfig.official_full_name || departmentIdForQuery} (Session: ${session.id}, Parl: ${parliamentNumberStr}) using effective date ${effectiveMinisterQueryDate.toISOString()}. Total minister records processed from query: ${allMinisterRecords.length}.`);
      return null;
    }

    candidates.sort((a, b) => {
      // Primary sort: latest positionStart (descending)
      if (a.positionStart.getTime() !== b.positionStart.getTime()) {
        return b.positionStart.getTime() - a.positionStart.getTime();
      }
      // Secondary sort: prefer no end date (considered later), then latest positionEnd (descending)
      if (!a.positionEnd && b.positionEnd) return -1; // a is better (no end date)
      if (a.positionEnd && !b.positionEnd) return 1;  // b is better (no end date)
      if (a.positionEnd && b.positionEnd) {
        if (a.positionEnd.getTime() !== b.positionEnd.getTime()) {
          return b.positionEnd.getTime() - a.positionEnd.getTime();
        }
      }
      // Tertiary sort: by name, as a stable fallback
      return (a.name || '').localeCompare(b.name || '');
    });
    
    const bestCandidate = candidates[0];
    console.log(`[Server Utils Info] Selected Minister for ${effectiveDeptConfigForName.official_full_name || departmentIdForQuery} (Session ${session.id}, Parl ${parliamentNumberStr}) using effective date ${effectiveMinisterQueryDate.toISOString()}: ${bestCandidate.name} - ${bestCandidate.title} (PosStart: ${bestCandidate.positionStart.toISOString()}, PosEnd: ${bestCandidate.positionEnd ? bestCandidate.positionEnd.toISOString() : 'N/A'})`);

    let finalAvatarUrl = bestCandidate.avatarUrl;
    if (!finalAvatarUrl) {
        const partyToAbbreviation: Record<string, string> = {
            "Liberal": "Lib", "Conservative": "CPC", "Conservative Party of Canada": "CPC",
            "New Democratic Party": "NDP", "Bloc Québécois": "BQ", "Green Party of Canada": "GP"
        };
        const partyAbbreviation = partyToAbbreviation[bestCandidate.party] || null;
        const parliamentIdForUrl = session.id;

        if (bestCandidate.lastName && bestCandidate.firstName && partyAbbreviation && parliamentIdForUrl) {
            const nameSlug = (bestCandidate.lastName + bestCandidate.firstName).replace(/\\s+/g, '');
            finalAvatarUrl = `https://www.ourcommons.ca/Content/Parliamentarians/Images/OfficialMPPhotos/${parliamentIdForUrl}/${nameSlug}_${partyAbbreviation}.jpg`;
            console.log(`[Server Utils Info] Constructed fallback avatar URL for ${bestCandidate.name}: ${finalAvatarUrl}`);
        } else {
            console.log(`[Server Utils Warn] Could not construct fallback avatar URL for ${bestCandidate.name}.`);
        }
    } else {
        console.log(`[Server Utils Info] Using avatar URL from department_ministers for ${bestCandidate.name}: ${finalAvatarUrl}`);
    }

    return {
      name: bestCandidate.name,
      firstName: bestCandidate.firstName,
      lastName: bestCandidate.lastName,
      party: bestCandidate.party,
      title: bestCandidate.title,
      avatarUrl: finalAvatarUrl || DEFAULT_PLACEHOLDER_AVATAR,
      positionStart: bestCandidate.positionStart.toISOString(),
      positionEnd: bestCandidate.positionEnd ? bestCandidate.positionEnd.toISOString() : null,
      effectiveDepartmentOfficialFullName: effectiveDeptConfigForName.official_full_name,
      effectiveDepartmentId: effectiveDeptConfigForName.id,
    };

  } catch (error) {
    console.error(`[Server Utils Error] Failed to fetch minister from 'department_ministers' for dept ${departmentIdForQuery} (parl ${parliamentNumberStr}):`, error);
    return null;
  }
} 