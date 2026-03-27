import { ImageResponse } from "next/og";
import { fetchApi } from "@/lib/api";
import type {
  CommitmentsResponse,
  DepartmentWithMinister,
} from "@/lib/commitment-types";
import {
  BuildCanadaBadge,
  fetchImageBase64,
  loadFonts,
  loadLogoBase64,
  OG_BG,
  OG_RED,
  OG_SIZE,
  StatusLegend,
  WaffleChart,
} from "@/lib/og-image";

export const alt = "Outcomes Tracker - Build Canada";
export const size = OG_SIZE;
export const contentType = "image/png";
export const revalidate = 14400; // regenerate every 4 hours

export default async function Image() {
  const [fonts, logoSrc] = await Promise.all([
    loadFonts(),
    Promise.resolve(loadLogoBase64()),
  ]);

  const [departments, commitmentsData] = await Promise.all([
    fetchApi<DepartmentWithMinister[]>("/api/v1/departments.json").catch(
      () => [] as DepartmentWithMinister[],
    ),
    fetchApi<CommitmentsResponse>(
      "/api/v1/commitments.json?per_page=1000",
    ).catch(() => ({
      commitments: [],
      meta: { total_count: 0, page: 1, per_page: 1000 },
    })),
  ]);

  const commitments = commitmentsData.commitments;

  const pmDept = departments.find(
    (d) => d.slug === "prime-minister-and-privy-council",
  );
  const pm = pmDept?.minister ?? null;
  const pmPhoto = pm?.avatar_url ? await fetchImageBase64(pm.avatar_url) : null;

  const counts: Record<string, number> = {};
  for (const c of commitments) {
    counts[c.status] = (counts[c.status] ?? 0) + 1;
  }

  return new ImageResponse(
    <div
      style={{
        display: "flex",
        width: 1200,
        height: 630,
        backgroundColor: OG_BG,
        fontFamily: "Inter",
        position: "relative",
      }}
    >
      <BuildCanadaBadge logoSrc={logoSrc} />

      {/* Left: PM photo filling full height */}
      <div
        style={{
          display: "flex",
          width: 300,
          height: 630,
          flexShrink: 0,
          overflow: "hidden",
        }}
      >
        {pmPhoto ? (
          <img
            src={pmPhoto}
            alt="Mark Carney"
            style={{
              width: 300,
              height: 630,
              objectFit: "cover",
              objectPosition: "center 15%",
            }}
          />
        ) : (
          <div
            style={{
              width: 300,
              height: 630,
              backgroundColor: OG_RED,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "white",
              fontSize: 80,
              fontWeight: 700,
            }}
          >
            MC
          </div>
        )}
      </div>

      {/* Right: content */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          flex: 1,
          padding: "28px 24px 24px 36px",
        }}
      >
        {/* Title */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            marginBottom: 22,
          }}
        >
          <span
            style={{
              fontSize: 72,
              fontWeight: 700,
              color: "#1a1a1a",
              lineHeight: 1.05,
              letterSpacing: "-0.02em",
            }}
          >
            Outcomes Tracker
          </span>
          <span
            style={{
              fontSize: 22,
              color: "#666",
              marginTop: 10,
            }}
          >
            Track the Canadian government&apos;s progress on key commitments
          </span>
        </div>

        {/* Waffle chart */}
        <div style={{ display: "flex", marginBottom: 14 }}>
          <WaffleChart commitments={commitments} maxWidth={840} />
        </div>

        {/* Status counts — pinned to bottom */}
        <div style={{ display: "flex", marginTop: "auto", paddingBottom: 14 }}>
          <StatusLegend counts={counts} />
        </div>
      </div>
    </div>,
    { ...size, fonts },
  );
}
