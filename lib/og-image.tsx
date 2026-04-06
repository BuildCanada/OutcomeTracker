import { readFileSync } from "fs";
import { join } from "path";
import type { CommitmentListing } from "./commitment-types";

export function loadLogoBase64(): string {
  const svg = readFileSync(
    join(process.cwd(), "public/buildcanada-logo-square.svg"),
  );
  return `data:image/svg+xml;base64,${Buffer.from(svg).toString("base64")}`;
}

export const OG_SIZE = { width: 1200, height: 630 };
export const OG_BG = "#f5ede3";
export const OG_RED = "#8b2332";

export const OG_COLORS: Record<string, string> = {
  not_started: "#d1d5db",
  in_progress: "#fbbf24",
  completed: "#356643",
  broken: "#8b2332",
};

const WAFFLE_ORDER = ["completed", "in_progress", "not_started", "broken"];

// Satori supports WOFF (not WOFF2). Old Safari UA causes Google Fonts to return WOFF.
async function fetchInterFont(weight: 400 | 700): Promise<ArrayBuffer | null> {
  try {
    const css = await fetch(
      `https://fonts.googleapis.com/css2?family=Inter:wght@${weight}&display=swap`,
      {
        headers: {
          "User-Agent":
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_2) AppleWebKit/536.26.17 (KHTML, like Gecko) Version/6.0.2 Safari/536.26.17",
        },
      },
    ).then((r) => r.text());

    const url = css.match(/src:\s*url\(([^)]+)\)/)?.[1];
    if (!url) return null;
    return fetch(url).then((r) => r.arrayBuffer());
  } catch {
    return null;
  }
}

export async function loadFonts() {
  const [normal, bold] = await Promise.all([
    fetchInterFont(400),
    fetchInterFont(700),
  ]);
  const fonts: { name: string; data: ArrayBuffer; weight: 400 | 700 }[] = [];
  if (normal) fonts.push({ name: "Inter", data: normal, weight: 400 });
  if (bold) fonts.push({ name: "Inter", data: bold, weight: 700 });
  return fonts;
}

export function sortByStatus(commitments: CommitmentListing[]) {
  return [...commitments].sort(
    (a, b) => WAFFLE_ORDER.indexOf(a.status) - WAFFLE_ORDER.indexOf(b.status),
  );
}

export async function fetchImageBase64(url: string): Promise<string | null> {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(4000) });
    if (!res.ok) return null;
    const buffer = await res.arrayBuffer();
    const base64 = Buffer.from(buffer).toString("base64");
    const ct = res.headers.get("content-type") || "image/jpeg";
    return `data:${ct};base64,${base64}`;
  } catch {
    return null;
  }
}

export function formatDate(date: Date) {
  return date.toLocaleDateString("en-CA", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

// Shared Build Canada badge — top right corner
export function BuildCanadaBadge({ logoSrc }: { logoSrc: string }) {
  return (
    <img
      src={logoSrc}
      alt="Build Canada"
      style={{
        position: "absolute",
        top: 24,
        right: 24,
        width: 130,
        height: 130,
      }}
    />
  );
}

// Reusable waffle chart for Satori
export function WaffleChart({
  commitments,
  maxWidth = 820,
}: {
  commitments: CommitmentListing[];
  maxWidth?: number;
}) {
  const sorted = sortByStatus(commitments);
  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: 2,
        maxWidth,
      }}
    >
      {sorted.map((c, i) => (
        <div
          key={i}
          style={{
            width: 20,
            height: 20,
            backgroundColor: OG_COLORS[c.status] ?? "#d1d5db",
            flexShrink: 0,
          }}
        />
      ))}
    </div>
  );
}

// Shared status legend row
export function StatusLegend({ counts }: { counts: Record<string, number> }) {
  const entries = [
    { key: "completed", label: "Completed", color: "#356643" },
    { key: "in_progress", label: "In Progress", color: "#fbbf24" },
    { key: "not_started", label: "Not Started", color: "#9ca3af" },
    { key: "broken", label: "Broken", color: "#8b2332" },
  ];
  return (
    <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
      {entries
        .filter(({ key }) => (counts[key] ?? 0) > 0)
        .map(({ key, label, color }) => (
          <div
            key={key}
            style={{ display: "flex", alignItems: "center", gap: 6 }}
          >
            <div
              style={{
                width: 28,
                height: 28,
                backgroundColor: color,
                flexShrink: 0,
              }}
            />
            <span style={{ fontSize: 26, color: "#555" }}>
              {counts[key]} {label}
            </span>
          </div>
        ))}
    </div>
  );
}
