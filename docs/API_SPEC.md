# API Spec (V1)

Base path: `/api/v1`

## Transition Status (2026-02-13)
- Direction is now scraper-first with county auction ingestion as primary source.
- RapidAPI-backed listings/metrics fields are deprecated and will be removed after scraper parity.
- Hunt County, TX is the first live county target.

## Endpoints

### `GET /opportunities`
Returns ranked opportunities with filters.

Query params:
- `min_score` (optional number)
- `max_price` (optional number, default `5000`)
- `county` (optional string)
- `page` (optional int, default `1`)
- `page_size` (optional int, default `25`, max `100`)

Response shape:
- `items: OpportunityListItem[]`
- `total: number`
- `page: number`
- `page_size: number`
- `generated_at: string (ISO datetime)`

### `GET /opportunities/{opportunity_id}`
Returns detailed opportunity payload.

Response includes:
- `opportunity: OpportunityDetail`
- `score_breakdown: ScoreBreakdown`
- `reason_codes: ReasonCode[]`
- `risk_flags: RiskFlag[]`
- `data_sources: SourceAttribution[]`

### `POST /opportunities/{opportunity_id}/feedback`
Stores thumbs up/down label.

Request:
- `vote: "up" | "down"`
- `note?: string`

Response:
- `status: "ok"`
- `feedback_id: string`

### `GET /digests/latest`
Returns most recent digest.

### `GET /digests`
Returns digest history list.

### `POST /jobs/run-daily`
Triggers manual run of daily pipeline.

Response:
- `run_id: string`
- `status: "success" | "degraded" | "failed"`

### `GET /runs`
Returns ETL run history and statuses.

Run status values:
- `running`
- `success`
- `degraded`
- `failed`

### `GET /settings`
Returns non-secret runtime settings and provider health.

Provider settings/health fields:
- `rapidapi_configured: boolean` (deprecated)
- `regrid_configured: boolean`
- `rapidapi_provider_slug: string` (deprecated)
- `rapidapi_metrics_slug: string` (deprecated)
- `listing_locations_count: number` (deprecated)
- `listing_page_limit: number` (deprecated)
- `listing_pages_per_location: number` (deprecated)
- `listing_sort: string` (deprecated)
- `listing_price_max: number` (deprecated)
- `auction_source_mode: string`
- `auction_csv_dir: string`
- `auction_csv_glob: string`
- `auction_max_file_age_days: number`
- `scraper_primary_source: string` (planned; `county_auction_scraper`)
- `scraper_target_counties: string[]` (planned; starts with `["Hunt County, TX"]`)
- `scraper_last_success_at: string | null` (planned ISO datetime)
- `scraper_parse_error_count: number` (planned)
- `provider_timeout_seconds: number`
- `provider_max_retries: number`
- `market_metrics_cache_lookback_days: number`
- `personalization_ready: boolean`
- `feedback_labels_count: number`
- `personalization_threshold: number`
- `personalization_blend_weight: number`
- `provider_health: ProviderEventStatus[]`

### `PUT /settings`
Updates non-secret runtime settings (schedule time, provider toggles).

Transition expectation:
- Existing deployments may still return only legacy RapidAPI settings fields until scraper settings are implemented.

## Core Types
- `OpportunityListItem`
  - `id`, `county`, `state`, `price`, `acreage`, `final_score`, `base_score`, `source_type`, `created_at`
- `OpportunityDetail`
  - `id`, `parcel_id`, `county`, `state`, `price`, `acreage`, `source_type`, `source_id`, `source_name`, `source_url`, `is_excluded`, `reason_codes`, `caution_code`, `model_version`, `blend_weight`, `score_breakdown`, `created_at`
- `ScoreBreakdown`
  - `market_growth_score`, `development_pressure_score`, `accessibility_score`, `liquidity_score`, `risk_penalty_score`, `base_score`, `final_score`, `personalization_score`
- `ReasonCode`
  - `code`, `label`, `direction` (`positive` or `caution`), `impact`
- `RunStatus`
  - `id`, `run_type`, `status`, `started_at`, `finished_at`, `listings_ingested`, `auctions_ingested`, `candidates_scored`, `excluded_count`, `error_summary`, `provider_events`
- `ProviderEventStatus`
  - `provider`, `status`, `error_summary`, `created_at`

## Error Contract
Consistent error envelope:
- `error.code`
- `error.message`
- `error.details` (optional object)

HTTP status usage:
- `400` validation error
- `404` not found
- `409` conflict/state error
- `500` internal processing error
