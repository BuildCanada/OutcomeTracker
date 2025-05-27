import { firestoreAdmin } from "@/lib/firebaseAdmin";
import { notFound } from "next/navigation";
import { Metadata } from "next";
import type { PromiseData, EvidenceItem } from "@/lib/types";
import { Timestamp } from "firebase-admin/firestore";
import PromiseDetailClient from "@/components/PromiseDetailClient";

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

// Helper to format Firestore Timestamp or ISO string date
const formatDate = (date: Timestamp | string | undefined): string => {
  if (!date) return "Date unknown";
  try {
    const jsDate = date instanceof Timestamp ? date.toDate() : new Date(date);
    return jsDate.toLocaleDateString("en-CA", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  } catch (e) {
    console.error("Error formatting date:", date, e);
    return typeof date === "string" ? date : "Invalid date";
  }
};

// Helper to format YYYY-MM-DD date string
const formatSimpleDate = (dateString: string | undefined): string => {
  if (!dateString) return "Date unknown";
  try {
    const [year, month, day] = dateString.split("-");
    const date = new Date(parseInt(year), parseInt(month) - 1, parseInt(day));
    return date.toLocaleDateString("en-CA", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  } catch (e) {
    console.error("Error formatting simple date:", dateString, e);
    return dateString;
  }
};

// Helper function to get SVG arc path for pie fill
function getPieArcPath(cx: number, cy: number, r: number, startAngle: number, endAngle: number): string {
  const start = polarToCartesian(cx, cy, r, endAngle);
  const end = polarToCartesian(cx, cy, r, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? "0" : "1";
  return [
    "M", cx, cy,
    "L", start.x, start.y,
    "A", r, r, 0, largeArcFlag, 0, end.x, end.y,
    "Z"
  ].join(" ");
}

function polarToCartesian(cx: number, cy: number, r: number, angleInDegrees: number): { x: number; y: number } {
  var angleInRadians = (angleInDegrees-90) * Math.PI / 180.0;
  return {
    x: cx + (r * Math.cos(angleInRadians)),
    y: cy + (r * Math.sin(angleInRadians))
  };
}

function getPieColor(progressScore: number): string {
  const colorMap = [
    '#ef4444', // red-500
    '#facc15', // yellow-400
    '#fde047', // yellow-300
    '#a3e635', // lime-400
    '#16a34a', // green-600
  ];
  return colorMap[Math.max(0, Math.min(progressScore - 1, 4))];
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

  return <PromiseDetailClient promise={promiseWithEvidence} />;
} 