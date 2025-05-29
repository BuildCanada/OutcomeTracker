import { firestoreAdmin } from "@/lib/firebaseAdmin";
import type { MinisterInfo, DepartmentConfig, ParliamentSession } from "@/lib/types";

// Default placeholder avatar, moved from page.tsx
const DEFAULT_PLACEHOLDER_AVATAR = "/placeholder.svg?height=100&width=100";

// Function to fetch minister details 
export async function fetchMinisterForDepartmentInSessionAdmin(
  departmentConfig: DepartmentConfig,
  session: ParliamentSession
): Promise<MinisterInfo | null> {
  if (!departmentConfig || !session) {
    console.error("[Server Utils Error] Missing required parameters: departmentConfig or session");
    return null;
  }

  if (!firestoreAdmin) {
    console.error("[Server Utils Error] Firestore admin not available");
    return null;
  }

  try {
    // Handle historical mappings
    let effectiveDeptConfigForQuery = departmentConfig;
    let effectiveDeptConfigForName = departmentConfig;
    
    const historicalMapping = departmentConfig.historical_mapping?.[session.id];
    
    if (historicalMapping && historicalMapping.minister_lookup_slug) {
      effectiveDeptConfigForQuery = departmentConfig;
      effectiveDeptConfigForQuery.id = historicalMapping.minister_lookup_slug;

      // Attempt to fetch the historical department config for its name, using the minister_lookup_slug as its ID
      try {
        const historicalDeptDoc = await firestoreAdmin.collection('department_config').doc(historicalMapping.minister_lookup_slug).get();
        if (historicalDeptDoc.exists) {
          effectiveDeptConfigForName = historicalDeptDoc.data() as DepartmentConfig;
          effectiveDeptConfigForName.id = historicalDeptDoc.id; // Ensure ID is part of the object
        }
      } catch (configError) {
        console.error(`[Server Utils Error] Error fetching historical DepartmentConfig for '${historicalMapping.minister_lookup_slug}':`, configError);
        // Continue with original departmentConfig for name if historical fetch fails
      }
    }

    const departmentIdForQuery = effectiveDeptConfigForQuery.id;
    const parliamentNumberStr = session.parliament_number.toString();

    const t0 = Date.now();
    const ministersQuery = firestoreAdmin
      .collection('department_ministers')
      .where('departmentId', '==', departmentIdForQuery)
      .where('parliamentNumber', '==', parliamentNumberStr)
      .orderBy('positionStart', 'desc');

    const ministersQuerySnapshot = await ministersQuery.get();

    if (ministersQuerySnapshot.docs.length === 0) {
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
        }
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
    console.error(`[Server Utils Error] Error in fetchMinisterForDepartmentInSessionAdmin:`, error);
    return null;
  }
} 