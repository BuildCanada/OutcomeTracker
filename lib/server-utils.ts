import { firestoreAdmin } from "@/lib/firebaseAdmin";
import type { MinisterInfo, DepartmentConfig, ParliamentSession } from "@/lib/types";

// Default placeholder avatar, moved from page.tsx
const DEFAULT_PLACEHOLDER_AVATAR = "/placeholder.svg?height=100&width=100";

// Function to fetch minister details (REVISED to use department_ministers)
// Moved from page.tsx
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

  const departmentId = departmentConfig.id;
  const parliamentNumber = String(session.parliament_number);

  let t0 = Date.now();
  try {
    const ministersQuerySnapshot = await firestoreAdmin
      .collection('department_ministers')
      .where('departmentId', '==', departmentId)
      .where('parliamentNumber', '==', parliamentNumber)
      .get();

    console.log(`[Server Utils LCP Timing] Query to 'department_ministers' for dept ${departmentId} (parl ${parliamentNumber}) took ${Date.now() - t0} ms. Found ${ministersQuerySnapshot.docs.length} potential records.`);

    if (ministersQuerySnapshot.empty) {
      console.log(`[Server Utils Info] No minister records found in 'department_ministers' for Dept ID: ${departmentId}, Parliament: ${parliamentNumber}.`);
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
          console.warn(`[Server Utils Warn] Minister record ${doc.id} for dept ${departmentId} missing or invalid positionStart.`);
          return null;
        }
        const posStartDate = new Date(posStartDateStr);
        const posEndDate = posEndDateStr && typeof posEndDateStr === 'string' ? new Date(posEndDateStr) : null;

        if (isNaN(posStartDate.getTime()) || (posEndDate && isNaN(posEndDate.getTime()))) {
          console.warn(`[Server Utils Warn] Minister record ${doc.id} for dept ${departmentId} has invalid date strings.`);
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
        console.error(`[Server Utils Error] Error processing minister record ${doc.id} for dept ${departmentId}:`, e);
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
        console.log(`[Server Utils Info] No minister found for Dept ${departmentId} using session_start_date (${session.start_date}). Trying election_date_preceding (${session.election_date_preceding}).`);
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
      console.log(`[Server Utils Info] No *active* minister found for Dept: ${departmentConfig.official_full_name || departmentId} (Session: ${session.id}, Parl: ${parliamentNumber}) using effective date ${effectiveMinisterQueryDate.toISOString()}. Total minister records processed from query: ${allMinisterRecords.length}.`);
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
    console.log(`[Server Utils Info] Selected Minister for ${departmentConfig.official_full_name || departmentId} (Session ${session.id}, Parl ${parliamentNumber}) using effective date ${effectiveMinisterQueryDate.toISOString()}: ${bestCandidate.name} - ${bestCandidate.title} (PosStart: ${bestCandidate.positionStart.toISOString()}, PosEnd: ${bestCandidate.positionEnd ? bestCandidate.positionEnd.toISOString() : 'N/A'})`);

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
    };

  } catch (error) {
    console.error(`[Server Utils Error] Failed to fetch minister from 'department_ministers' for dept ${departmentId} (parl ${parliamentNumber}):`, error);
    return null;
  }
} 