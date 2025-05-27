import { firestoreAdmin } from "@/lib/firebaseAdmin";
import { notFound } from "next/navigation";
import { Metadata } from "next";
import type { PromiseData, EvidenceItem } from "@/lib/types";
import { Timestamp } from "firebase-admin/firestore";

interface Props {
  params: Promise<{ promiseId: string }>;
}

// Helper function to serialize Firestore data recursively
function serializeFirestoreData(data: any): any {
  if (!data) return data;
  
  if (data instanceof Timestamp) {
    return data.toDate().toISOString();
  }
  
  if (Array.isArray(data)) {
    return data.map(item => serializeFirestoreData(item));
  }
  
  if (typeof data === 'object' && data !== null) {
    const serialized: any = {};
    for (const [key, value] of Object.entries(data)) {
      serialized[key] = serializeFirestoreData(value);
    }
    return serialized;
  }
  
  return data;
}

async function getPromiseData(promiseId: string): Promise<{
  promise: PromiseData | null;
  evidence: EvidenceItem[];
}> {
  try {
    // Fetch the specific promise document
    const promiseDoc = await firestoreAdmin
      .collection("promises")
      .doc(promiseId)
      .get();

    if (!promiseDoc.exists) {
      return { promise: null, evidence: [] };
    }

    const promiseData = promiseDoc.data();
    if (!promiseData) {
      return { promise: null, evidence: [] };
    }

    // Serialize the promise data recursively
    const serializedPromiseData = serializeFirestoreData(promiseData);
    const promise: PromiseData = {
      id: promiseDoc.id,
      ...serializedPromiseData,
    };

    // Fetch related evidence items
    const evidenceQuery = await firestoreAdmin
      .collection("evidence_items")
      .where("promise_ids", "array-contains", promiseId)
      .orderBy("evidence_date", "desc")
      .get();

    const evidence: EvidenceItem[] = evidenceQuery.docs.map(doc => {
      const evidenceData = doc.data();
      const serializedEvidenceData = serializeFirestoreData(evidenceData);
      return {
        id: doc.id,
        evidence_id: doc.id,
        ...serializedEvidenceData,
      };
    });

    return { promise, evidence };
  } catch (error) {
    console.error("Error fetching promise data:", error);
    return { promise: null, evidence: [] };
  }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { promiseId } = await params;
  const { promise } = await getPromiseData(promiseId);
  
  if (!promise) {
    return {
      title: "Promise Not Found | Build Canada Tracker",
      description: "The requested promise could not be found.",
    };
  }

  const title = promise.concise_title || promise.text;
  const rawDescription = promise.intended_impact_and_objectives || 
                        promise.what_it_means_for_canadians || 
                        promise.text;

  // Convert description to string and truncate
  const descriptionString = Array.isArray(rawDescription) 
    ? rawDescription.join(' ') 
    : String(rawDescription || "Government promise tracking");
  
  const truncatedDescription = descriptionString.length > 160 
    ? descriptionString.substring(0, 157) + "..." 
    : descriptionString;

  const truncatedTitle = title.length > 60 
    ? title.substring(0, 57) + "..." 
    : title;

  const fullTitle = `${truncatedTitle} | Build Canada Tracker`;
  
  // Construct the canonical URL
  const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || "https://buildcanada.ca";
  const canonicalUrl = `${baseUrl}/promise/${promiseId}`;

  return {
    title: fullTitle,
    description: truncatedDescription,
    openGraph: {
      type: "article",
      url: canonicalUrl,
      title: fullTitle,
      description: truncatedDescription,
      siteName: "Build Canada Tracker",
      images: [
        {
          url: `${baseUrl}/og-image.png`, // You'll need to add this image
          width: 1200,
          height: 630,
          alt: "Build Canada Tracker - Government Promise Tracking",
        },
      ],
      locale: "en_CA",
    },
    twitter: {
      card: "summary_large_image",
      title: fullTitle,
      description: truncatedDescription,
      images: [`${baseUrl}/og-image.png`],
      site: "@BuildCanada", // Add your Twitter handle if you have one
    },
    alternates: {
      canonical: canonicalUrl,
    },
    robots: {
      index: true,
      follow: true,
    },
  };
}

// Simple client component for displaying promise details
function PromiseDetailView({ promise }: { promise: PromiseData }) {
  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
          <div className="p-6">
            <h1 className="text-3xl font-bold text-gray-900 mb-4">
              {promise.concise_title || promise.text}
            </h1>
            
            {promise.intended_impact_and_objectives && (
              <div className="mb-6">
                <h2 className="text-xl font-semibold text-gray-800 mb-2">Impact and Objectives</h2>
                <p className="text-gray-700">{promise.intended_impact_and_objectives}</p>
              </div>
            )}
            
            {promise.what_it_means_for_canadians && (
              <div className="mb-6">
                <h2 className="text-xl font-semibold text-gray-800 mb-2">What This Means for Canadians</h2>
                <div className="text-gray-700">
                  {Array.isArray(promise.what_it_means_for_canadians) ? (
                    <ul className="list-disc pl-5 space-y-2">
                      {promise.what_it_means_for_canadians.map((item, index) => (
                        <li key={index}>{item}</li>
                      ))}
                    </ul>
                  ) : (
                    <p>{promise.what_it_means_for_canadians}</p>
                  )}
                </div>
              </div>
            )}
            
            {promise.progress_summary && (
              <div className="mb-6">
                <h2 className="text-xl font-semibold text-gray-800 mb-2">Progress</h2>
                <p className="text-gray-700">{promise.progress_summary}</p>
              </div>
            )}
            
            <div className="text-sm text-gray-500">
              <p>Department: {promise.responsible_department_lead}</p>
              {promise.category && <p>Category: {promise.category}</p>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default async function PromiseDetailPage({ params }: Props) {
  const { promiseId } = await params;
  const { promise, evidence } = await getPromiseData(promiseId);

  if (!promise) {
    notFound();
  }

  // Add evidence to promise object for compatibility with existing components
  const promiseWithEvidence: PromiseData = {
    ...promise,
    evidence,
  };

  return <PromiseDetailView promise={promiseWithEvidence} />;
} 