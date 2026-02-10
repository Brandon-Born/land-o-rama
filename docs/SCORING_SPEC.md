# Scoring and Exclusion Spec (V1)

## Candidate Prefilter
- Accept vacant land/lot categories only.
- Primary target: list price `<= $5,000`.
- Keep contextual near-threshold records up to `$6,000` for comps only.

## Hard Exclusions (Strict)
Any of the following removes a parcel from ranked output:
- No legal road access.
- Severe flood/wetland constraints beyond threshold.
- Zoning clearly incompatible with buildable residential use.
- Missing critical fields after normalization (price, location, parcel ID, county).
- Invalid or duplicate parcel identity that cannot be resolved.

## Feature Buckets (0-100)
- `market_growth_score`
  - County-level population/jobs/permits trend proxies.
- `development_pressure_score`
  - Indicators of expanding nearby development activity.
- `accessibility_score`
  - Road access quality and proximity proxies to services/towns.
- `liquidity_score`
  - Turnover and marketability proxies (listing dynamics).
- `risk_penalty_score`
  - Non-fatal risk burden (higher = worse risk).

## Base Score Formula
```text
base_score =
  0.35 * market_growth_score +
  0.25 * development_pressure_score +
  0.20 * accessibility_score +
  0.10 * liquidity_score +
  0.10 * (100 - risk_penalty_score)
```

## Value Context Modifier
- Compare price-per-acre within county peer bucket.
- Apply modifier in range `[-10, +10]` points.
- Goal: reward relatively cheap parcels versus local comparables.

## Feedback Personalization
- Before 50 labels: ignore personalization model.
- At/after 50 labels: train nightly logistic model from thumbs up/down labels.
- Final score:
```text
final_score = 0.85 * base_score + 0.15 * personalization_score
```

## Explainability Output
Each surfaced opportunity must expose:
- Final score.
- Factor breakdown by bucket.
- Top 3 positive reason codes.
- Top 1 caution reason code.
- Data freshness timestamp.

## Tuning Rules
- Do not change weights without updating this file.
- Any threshold change requires corresponding test updates.
- Maintain deterministic outputs given fixed inputs.
