# API Spec (V1)

Base path: `/api/v1`

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
- `status: "queued" | "running"`

### `GET /runs`
Returns ETL run history and statuses.

### `GET /settings`
Returns non-secret runtime settings and provider health.

### `PUT /settings`
Updates non-secret runtime settings (schedule time, provider toggles).

## Core Types
- `OpportunityListItem`
  - `id`, `title`, `county`, `price`, `acres`, `final_score`, `is_excluded`, `created_at`
- `OpportunityDetail`
  - `id`, `parcel_id`, `coordinates`, `zoning`, `access_type`, `utilities_hint`, `listing_summary`
- `ScoreBreakdown`
  - `market_growth_score`, `development_pressure_score`, `accessibility_score`, `liquidity_score`, `risk_penalty_score`, `base_score`, `final_score`
- `ReasonCode`
  - `code`, `label`, `direction` (`positive` or `caution`), `impact`
- `RiskFlag`
  - `flag`, `severity`, `is_exclusionary`
- `SourceAttribution`
  - `source_name`, `as_of`, `confidence`

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
