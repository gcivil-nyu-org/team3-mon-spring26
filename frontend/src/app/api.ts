/**
 * Django API base URL.
 * - Empty string: same origin (e.g. Vite proxy or static files served by Django).
 * - Or set VITE_API_BASE_URL=http://127.0.0.1:8000 when the SPA runs on another port.
 */
export function getApiBase(): string {
  return (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";
}

export function apiUrl(path: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${getApiBase()}${p}`;
}

export async function apiFetch(
  path: string,
  init?: RequestInit
): Promise<Response> {
  return fetch(apiUrl(path), {
    credentials: "include",
    ...init,
  });
}

/** Map page "Sort by" control values → Django `sort_by` query param. */
export function mapSortByToApi(uiValue: string): string {
  const m: Record<string, string> = {
    "composite-high-low": "composite_desc",
    "composite-low-high": "composite_asc",
    "name-a-z": "name_asc",
    "name-z-a": "name_desc",
  };
  return m[uiValue] ?? "composite_desc";
}
