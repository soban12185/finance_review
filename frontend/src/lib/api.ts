const BASE = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const body = options?.body;
  const headers: Record<string, string> = {
    ...(body && !(body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
    ...((options?.headers as Record<string, string>) ?? {}),
  };
  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else detail = JSON.stringify(body?.detail ?? body);
    } catch {
      /* keep status fallback */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

function qs(params: Record<string, string | number | undefined | null>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  return parts.length ? `?${parts.join("&")}` : "";
}

export interface TransactionParams {
  month?: string;
  category?: string;
  pnl_type?: string;
  review_status?: string;
  search?: string;
  method?: string;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
  limit?: number;
  offset?: number;
}

export const api = {
  dashboard: (month?: string) =>
    request<import("./types").DashboardData>(`/api/dashboard${qs({ month })}`),

  transactions: (p: TransactionParams = {}) =>
    request<import("./types").TransactionPage>(`/api/transactions${qs(p as Record<string, string | number>)}`),

  transaction: (id: string) => request(`/api/transactions/${encodeURIComponent(id)}`),

  meta: () =>
    request<{
      months: string[];
      categories: { category_code: string; category_name: string; count: number }[];
      methods: string[];
      pnl_types: string[];
    }>("/api/transactions/meta/filters"),

  categories: () => request<import("./types").Category[]>("/api/categories"),

  nonPnlCategories: () =>
    request<{ code: string; name: string; accounting_treatment: string }[]>("/api/categories/non-pnl"),

  pnl: (month: string) => request<import("./types").PnlReport>(`/api/pnl/${month}`),

  drilldown: (month: string, line: string) =>
    request<import("./types").PnlDrilldown>(`/api/pnl/${month}/drilldown/${encodeURIComponent(line)}`),

  months: () => request<string[]>("/api/pnl/months/available"),

  variance: (monthA: string, monthB: string) =>
    request<import("./types").VarianceReport>(`/api/variance${qs({ month_a: monthA, month_b: monthB })}`),

  varianceDrivers: (monthA: string, monthB: string, line: string) =>
    request<import("./types").VarianceDriverReport>(
      `/api/variance/drivers${qs({ month_a: monthA, month_b: monthB, line }) as string}`,
    ),

  reviews: (status?: string) =>
    request<import("./types").ReviewList>(`/api/reviews${qs({ status })}`),

  resolveReview: (id: number, body: { action: string; category_code?: string; note?: string; actor: string }) =>
    request<import("./types").ReviewItem>(`/api/reviews/${id}/resolve`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  analystChat: (question: string, history?: { role: string; content: string }[]) =>
    request<import("./types").AnalystResponse>("/api/analyst/chat", {
      method: "POST",
      body: JSON.stringify({ question, history }),
    }),

  analystHealth: () =>
    request<{ configured: boolean; model: string }>("/api/analyst/health"),

  ingest: (file: File, filename?: string) => {
    const form = new FormData();
    form.append("file", file, filename ?? file.name);
    return request<import("./types").IngestSummary>("/api/ingest/upload", { method: "POST", body: form });
  },

  ingestSample: () => request<import("./types").IngestSummary>("/api/ingest/sample", { method: "POST" }),
};