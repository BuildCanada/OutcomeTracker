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

export const alt = "Ministry - Outcomes Tracker";
export const size = OG_SIZE;
export const contentType = "image/png";
export const revalidate = 14400; // regenerate every 4 hours

export default async function Image({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const [fonts, logoSrc] = await Promise.all([
    loadFonts(),
    Promise.resolve(loadLogoBase64()),
  ]);

  const [departments, commitmentsData] = await Promise.all([
    fetchApi<DepartmentWithMinister[]>("/api/v1/departments.json").catch(
      () => [] as DepartmentWithMinister[],
    ),
    fetchApi<CommitmentsResponse>(
      `/api/v1/commitments.json?per_page=1000&lead_department=${slug}`,
    ).catch(() => ({
      commitments: [],
      meta: { total_count: 0, page: 1, per_page: 1000 },
    })),
  ]);

  const dept = departments.find((d) => d.slug === slug);
  const minister = dept?.minister ?? null;
  const ministryName =
    dept?.display_name ??
    slug.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  const commitments = commitmentsData.commitments;
  const totalCount = commitments.length;

  const statusCounts: Record<string, number> = {};
  for (const c of commitments) {
    statusCounts[c.status] = (statusCounts[c.status] ?? 0) + 1;
  }

  const ministerPhoto = minister?.avatar_url
    ? await fetchImageBase64(minister.avatar_url)
    : null;
  const ministerName = minister
    ? `${minister.first_name} ${minister.last_name}`
    : null;

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

      {/* Left: minister photo filling full height */}
      <div
        style={{
          display: "flex",
          width: 300,
          height: 630,
          flexShrink: 0,
          overflow: "hidden",
        }}
      >
        {ministerPhoto ? (
          <img
            src={ministerPhoto}
            alt={ministerName ?? "Minister"}
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
              fontSize: 72,
              fontWeight: 700,
            }}
          >
            {ministerName
              ? `${ministerName.split(" ")[0][0]}${ministerName.split(" ").at(-1)?.[0] ?? ""}`
              : "?"}
          </div>
        )}
      </div>

      {/* Right: content */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          flex: 1,
          padding: "36px 100px 32px 36px",
        }}
      >
        {/* Ministry name */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            marginBottom: 20,
          }}
        >
          <span
            style={{
              fontSize: 18,
              color: OG_RED,
              fontWeight: 700,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              marginBottom: 8,
            }}
          >
            Outcomes Tracker
          </span>
          <span
            style={{
              fontSize: 60,
              fontWeight: 700,
              color: "#1a1a1a",
              lineHeight: 1.05,
              letterSpacing: "-0.01em",
            }}
          >
            {ministryName}
          </span>
          <span
            style={{
              fontSize: 20,
              color: "#777",
              marginTop: 8,
            }}
          >
            {totalCount} commitment{totalCount !== 1 ? "s" : ""}
          </span>
        </div>

        {/* Waffle chart */}
        <div style={{ display: "flex", marginBottom: 18 }}>
          <WaffleChart commitments={commitments} maxWidth={840} />
        </div>

        {/* Status legend */}
        <div style={{ display: "flex", marginBottom: "auto" }}>
          <StatusLegend counts={statusCounts} />
        </div>
      </div>
    </div>,
    { ...size, fonts },
  );
}
