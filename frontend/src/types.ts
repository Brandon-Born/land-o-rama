export type OpportunityListItem = {
  id: string;
  county: string;
  state: string;
  price: number;
  acreage: number;
  final_score: number;
  base_score: number;
  source_type: string;
  created_at: string;
};

export type OpportunityListResponse = {
  items: OpportunityListItem[];
  total: number;
  page: number;
  page_size: number;
  generated_at: string;
};

export type ScoreBreakdown = {
  market_growth_score: number;
  development_pressure_score: number;
  accessibility_score: number;
  liquidity_score: number;
  risk_penalty_score: number;
  base_score: number;
  final_score: number;
};

export type OpportunityDetail = {
  id: string;
  parcel_id: string;
  county: string;
  state: string;
  price: number;
  acreage: number;
  source_type: string;
  source_id: string;
  is_excluded: boolean;
  exclusion_reason: string | null;
  reason_codes: Array<{ code: string; label: string; direction: string; impact: number }>;
  caution_code: { code: string; label: string; direction: string; impact: number } | null;
  score_breakdown: ScoreBreakdown;
  created_at: string;
};

export type DigestSummary = {
  id: string;
  generated_at: string;
  summary: string;
  opportunity_ids: string[];
};

export type DigestsResponse = {
  items: DigestSummary[];
};

export type RunStatus = {
  provider_events: ProviderEventStatus[];
  id: string;
  run_type: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  listings_ingested: number;
  auctions_ingested: number;
  candidates_scored: number;
  excluded_count: number;
  error_summary: string | null;
};

export type RunsResponse = {
  items: RunStatus[];
};

export type SettingsResponse = {
  state: string;
  refresh_time: string;
  mock_mode: boolean;
  disclaimers_enabled: boolean;
  rapidapi_configured: boolean;
  regrid_configured: boolean;
  rapidapi_provider_slug: string;
  rapidapi_metrics_slug: string;
  provider_timeout_seconds: number;
  provider_max_retries: number;
  market_metrics_cache_lookback_days: number;
  provider_health: ProviderEventStatus[];
};

export type ProviderEventStatus = {
  provider: string;
  status: string;
  error_summary: string | null;
  created_at: string;
};
