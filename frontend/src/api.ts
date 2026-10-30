export class ApiError extends Error { constructor(public status: number, msg: string) { super(msg); } }

export async function api<T = any>(path: string, opts: { method?: string; body?: any; form?: FormData } = {}): Promise<T> {
  const init: RequestInit = { method: opts.method || (opts.body || opts.form ? "POST" : "GET"), credentials: "same-origin" };
  if (opts.form) init.body = opts.form;
  else if (opts.body !== undefined) { init.body = JSON.stringify(opts.body); init.headers = { "Content-Type": "application/json" }; }
  const r = await fetch(`/api${path}`, init);
  if (!r.ok) {
    let msg = r.statusText;
    try { const j = await r.json(); msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch {}
    // Session gone (signed out elsewhere, expired, or data reset): send the user back to sign-in with a message.
    if (r.status === 401 && !path.startsWith("/auth/")) dispatchEvent(new CustomEvent("session-expired"));
    else if (init.method !== "GET" && !path.startsWith("/auth/")) dispatchEvent(new CustomEvent("api-error", { detail: msg }));
    throw new ApiError(r.status, msg);
  }
  return r.json();
}

export const go = (path: string) => { location.hash = path; };

export const fmtDate = (s?: string | null) => (s ? new Date(s.endsWith("Z") || s.length <= 10 ? s : s + "Z").toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "—");
export const fmtTime = (s?: string | null) => (s ? new Date(s.endsWith("Z") ? s : s + "Z").toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—");
