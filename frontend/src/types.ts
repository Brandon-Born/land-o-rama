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
  personalization_score: number | null;
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
  source_name: string | null;
  source_url: string | null;
  is_excluded: boolean;
  exclusion_reason: string | null;
  reason_codes: Array<{ code: string; label: string; direction: string; impact: number }>;
  caution_code: { code: string; label: string; direction: string; impact: number } | null;
  model_version: string | null;
  blend_weight: number;
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
  regrid_configured: boolean;
  price_cap: number;
  ingestion_price_cap: number;
  auction_source_mode: string;
  auction_csv_dir: string;
  auction_csv_glob: string;
  auction_max_file_age_days: number;
  provider_timeout_seconds: number;
  provider_max_retries: number;
  market_metrics_cache_lookback_days: number;
  scraper_primary_source: string;
  scraper_mode: string;
  scraper_target_counties: string[];
  scraper_last_success_at: string | null;
  scraper_last_success_county: string | null;
  scraper_parse_error_count: number;
  scraper_last_records_accepted: number;
  scraper_enabled_counties: string[];
  scraper_county_coverage: ScraperCountyCoverage[];
  scraper_county_failures: number;
  personalization_ready: boolean;
  feedback_labels_count: number;
  personalization_threshold: number;
  personalization_blend_weight: number;
  provider_health: ProviderEventStatus[];
};

export type ScraperCountyCoverage = {
  county: string;
  last_success_at: string | null;
  records_found: number;
  records_accepted: number;
  records_rejected: number;
  min_price: number | null;
  median_price: number | null;
  max_price: number | null;
  status: string;
};

export type ProviderEventStatus = {
  provider: string;
  status: string;
  error_summary: string | null;
  created_at: string;
};
