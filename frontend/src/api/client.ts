import type {
  DigestsResponse,
  OpportunityDetail,
  OpportunityListResponse,
  RunsResponse,
  SettingsResponse,
} from "../types";

const BASE = "http://localhost:8000/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
    },
    ...init,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Request failed");
  }
  return (await response.json()) as T;
}

export type OpportunityQueryParams = {
  county?: string;
  minScore?: number;
  maxPrice?: number;
  page?: number;
  pageSize?: number;
};

export function fetchOpportunities(params?: OpportunityQueryParams): Promise<OpportunityListResponse> {
  const query = new URLSearchParams();
  if (params?.county) query.set("county", params.county);
  if (params?.minScore !== undefined) query.set("min_score", String(params.minScore));
  if (params?.maxPrice !== undefined) query.set("max_price", String(params.maxPrice));
  if (params?.page !== undefined) query.set("page", String(params.page));
  if (params?.pageSize !== undefined) query.set("page_size", String(params.pageSize));
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return request<OpportunityListResponse>(`/opportunities${suffix}`);
}

export function fetchOpportunity(id: string): Promise<OpportunityDetail> {
  return request<OpportunityDetail>(`/opportunities/${id}`);
}

export function postFeedback(id: string, vote: "up" | "down"): Promise<{ status: string; feedback_id: string }> {
  return request(`/opportunities/${id}/feedback`, {
    method: "POST",
    body: JSON.stringify({ vote }),
  });
}

export function fetchLatestDigest(): Promise<{ id: string; generated_at: string; summary: string; opportunity_ids: string[] }> {
  return request("/digests/latest");
}

export function fetchDigests(): Promise<DigestsResponse> {
  return request<DigestsResponse>("/digests");
}

export function fetchRuns(): Promise<RunsResponse> {
  return request<RunsResponse>("/runs");
}

export function runDailyJob(): Promise<{ run_id: string; status: string }> {
  return request("/jobs/run-daily", { method: "POST" });
}

export function fetchSettings(): Promise<SettingsResponse> {
  return request<SettingsResponse>("/settings");
}
