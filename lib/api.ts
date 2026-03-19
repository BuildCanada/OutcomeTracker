// API_URL is for server-side fetches (runtime). NEXT_PUBLIC_API_URL is baked in at build time.
const API_BASE =
  process.env.API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:5000";

export async function fetchApi<T>(path: string): Promise<T> {
  // Strip basePath prefix if present
  if (path.startsWith("/tracker")) {
    path = path.slice("/tracker".length);
  }

  let url: string;
  if (path.startsWith("/api/v1/")) {
    // Rewrite: /api/v1/commitments.json -> ${API_BASE}/commitments.json
    url = `${API_BASE}/${path.slice("/api/v1/".length)}`;
  } else if (path.startsWith("/api/")) {
    // Rewrite: /api/burndown/1 -> ${API_BASE}/api/burndown/1
    url = `${API_BASE}${path}`;
  } else {
    url = `${API_BASE}${path}`;
  }

  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${res.status}: ${url}`);
  return res.json();
}
