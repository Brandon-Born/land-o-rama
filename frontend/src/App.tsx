import { useEffect, useMemo, useState } from "react";

import {
  fetchDigests,
  fetchLatestDigest,
  fetchOpportunity,
  fetchOpportunities,
  fetchRuns,
  fetchSettings,
  postFeedback,
  runDailyJob,
} from "./api/client";
import type {
  DigestSummary,
  OpportunityDetail,
  OpportunityListItem,
  ProviderEventStatus,
  RunStatus,
  SettingsResponse,
} from "./types";

type TabId = "dashboard" | "digest" | "runs";

type DashboardQuery = {
  county: string;
  minScore: number | null;
  maxPrice: number;
  page: number;
  pageSize: number;
};

type FilterErrors = {
  minScore: string | null;
  maxPrice: string | null;
};

const DEFAULT_QUERY: DashboardQuery = {
  county: "",
  minScore: null,
  maxPrice: 5000,
  page: 1,
  pageSize: 25,
};

function currency(value: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(
    value,
  );
}

function scoreClass(value: number): string {
  if (value >= 80) return "score-high";
  if (value >= 65) return "score-mid";
  return "score-low";
}

function parsePositiveInt(value: string | null, fallback: number): number {
  if (!value) return fallback;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function parseOptionalNumber(value: string | null): number | null {
  if (!value) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function validateFilters(minScoreInput: string, maxPriceInput: string): FilterErrors {
  const minScoreText = minScoreInput.trim();
  const maxPriceText = maxPriceInput.trim();

  let minScoreError: string | null = null;
  if (minScoreText) {
    const minScore = Number(minScoreText);
    if (!Number.isFinite(minScore)) {
      minScoreError = "Min score must be a number between 0 and 100.";
    } else if (minScore < 0 || minScore > 100) {
      minScoreError = "Min score must be between 0 and 100.";
    }
  }

  let maxPriceError: string | null = null;
  if (!maxPriceText) {
    maxPriceError = "Max price is required.";
  } else {
    const maxPrice = Number(maxPriceText);
    if (!Number.isFinite(maxPrice) || maxPrice <= 0) {
      maxPriceError = "Max price must be greater than 0.";
    }
  }

  return {
    minScore: minScoreError,
    maxPrice: maxPriceError,
  };
}

function readUrlState(): { query: DashboardQuery; tab: TabId } {
  const search = new URLSearchParams(window.location.search);
  const tabParam = search.get("tab");
  const tab: TabId = tabParam === "digest" || tabParam === "runs" ? tabParam : "dashboard";

  const county = (search.get("county") ?? "").trim();
  const minScore = parseOptionalNumber(search.get("minScore"));
  const maxPrice = parsePositiveInt(search.get("maxPrice"), DEFAULT_QUERY.maxPrice);
  const page = parsePositiveInt(search.get("page"), DEFAULT_QUERY.page);
  const pageSize = parsePositiveInt(search.get("pageSize"), DEFAULT_QUERY.pageSize);

  return {
    tab,
    query: {
      county,
      minScore,
      maxPrice,
      page,
      pageSize,
    },
  };
}

function writeUrlState(query: DashboardQuery, tab: TabId): void {
  const search = new URLSearchParams();
  if (query.county) search.set("county", query.county);
  if (query.minScore !== null) search.set("minScore", String(query.minScore));
  if (query.maxPrice !== DEFAULT_QUERY.maxPrice) search.set("maxPrice", String(query.maxPrice));
  if (query.page !== DEFAULT_QUERY.page) search.set("page", String(query.page));
  if (query.pageSize !== DEFAULT_QUERY.pageSize) search.set("pageSize", String(query.pageSize));
  if (tab !== "dashboard") search.set("tab", tab);

  const next = `${window.location.pathname}${search.toString() ? `?${search.toString()}` : ""}`;
  window.history.replaceState(null, "", next);
}

export default function App() {
  const initial = readUrlState();
  const [opportunities, setOpportunities] = useState<OpportunityListItem[]>([]);
  const [opportunityTotal, setOpportunityTotal] = useState<number>(0);
  const [selected, setSelected] = useState<OpportunityDetail | null>(null);
  const [latestDigest, setLatestDigest] = useState<DigestSummary | null>(null);
  const [digests, setDigests] = useState<DigestSummary[]>([]);
  const [runs, setRuns] = useState<RunStatus[]>([]);
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [query, setQuery] = useState<DashboardQuery>(initial.query);
  const [filterCounty, setFilterCounty] = useState<string>(initial.query.county);
  const [filterMinScore, setFilterMinScore] = useState<string>(
    initial.query.minScore === null ? "" : String(initial.query.minScore),
  );
  const [filterMaxPrice, setFilterMaxPrice] = useState<string>(String(initial.query.maxPrice));
  const [filterErrors, setFilterErrors] = useState<FilterErrors>({ minScore: null, maxPrice: null });
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>(initial.tab);
  const [runState, setRunState] = useState<string>("");

  async function loadAll(currentQuery: DashboardQuery) {
    setLoading(true);
    setError(null);
    try {
      const [opportunitiesResponse, latestDigestResponse, digestsResponse, runsResponse, settingsResponse] =
        await Promise.all([
          fetchOpportunities({
            county: currentQuery.county || undefined,
            minScore: currentQuery.minScore ?? undefined,
            maxPrice: currentQuery.maxPrice,
            page: currentQuery.page,
            pageSize: currentQuery.pageSize,
          }),
          fetchLatestDigest(),
          fetchDigests(),
          fetchRuns(),
          fetchSettings(),
        ]);
      setOpportunities(opportunitiesResponse.items);
      setOpportunityTotal(opportunitiesResponse.total);
      setLatestDigest(latestDigestResponse);
      setDigests(digestsResponse.items);
      setRuns(runsResponse.items);
      setSettings(settingsResponse);
      if (opportunitiesResponse.items.length > 0) {
        const detail = await fetchOpportunity(opportunitiesResponse.items[0].id);
        setSelected(detail);
      } else {
        setSelected(null);
      }
    } catch (loadError) {
      setError((loadError as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadAll(query);
  }, [query]);

  useEffect(() => {
    writeUrlState(query, activeTab);
  }, [activeTab, query]);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setFilterErrors(validateFilters(filterMinScore, filterMaxPrice));
    }, 300);
    return () => window.clearTimeout(timeout);
  }, [filterMinScore, filterMaxPrice]);

  const kpis = useMemo(() => {
    const total = opportunities.length;
    const avgScore =
      total > 0 ? opportunities.reduce((sum, item) => sum + item.final_score, 0) / total : 0;
    const under4k = opportunities.filter((item) => item.price < 4000).length;
    return { total, avgScore, under4k };
  }, [opportunities]);

  const providerHealth = useMemo(() => settings?.provider_health ?? [], [settings]);
  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(opportunityTotal / query.pageSize)),
    [opportunityTotal, query.pageSize],
  );
  const canApplyFilters = !filterErrors.minScore && !filterErrors.maxPrice;

  async function selectOpportunity(id: string) {
    try {
      const detail = await fetchOpportunity(id);
      setSelected(detail);
      setError(null);
    } catch (selectError) {
      setError((selectError as Error).message);
    }
  }

  async function submitVote(vote: "up" | "down") {
    if (!selected) return;
    try {
      await postFeedback(selected.id, vote);
      setRunState(`Feedback saved: ${vote}`);
    } catch (voteError) {
      setError((voteError as Error).message);
    }
  }

  async function triggerRun() {
    setRunState("Running daily scan...");
    try {
      const result = await runDailyJob();
      setRunState(`Run ${result.run_id} finished with status: ${result.status}`);
      await loadAll(query);
    } catch (runError) {
      setError((runError as Error).message);
      setRunState("Run failed");
    }
  }

  async function refreshDashboard() {
    await loadAll(query);
  }

  function applyFilters() {
    const nextErrors = validateFilters(filterMinScore, filterMaxPrice);
    setFilterErrors(nextErrors);
    if (nextErrors.minScore || nextErrors.maxPrice) {
      return;
    }
    const minScore = parseOptionalNumber(filterMinScore.trim() || null);
    const maxPriceInput = Number(filterMaxPrice.trim());
    setQuery((previous) => ({
      ...previous,
      county: filterCounty.trim(),
      minScore,
      maxPrice: maxPriceInput,
      page: 1,
    }));
  }

  function resetFilters() {
    setFilterCounty(DEFAULT_QUERY.county);
    setFilterMinScore("");
    setFilterMaxPrice(String(DEFAULT_QUERY.maxPrice));
    setFilterErrors({ minScore: null, maxPrice: null });
    setQuery({ ...DEFAULT_QUERY, pageSize: query.pageSize });
  }

  function goToPage(nextPage: number) {
    setQuery((previous) => ({
      ...previous,
      page: Math.max(1, Math.min(nextPage, totalPages)),
    }));
  }

  function updatePageSize(nextPageSize: number) {
    setQuery((previous) => ({
      ...previous,
      pageSize: nextPageSize,
      page: 1,
    }));
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <h1>Land-O-Rama</h1>
          <p>Texas sub-$5k land scanner with 5-year upside scoring and strict risk exclusions.</p>
        </div>
        <div className="controls">
          <button onClick={() => void refreshDashboard()}>Refresh</button>
          <button className="primary" onClick={() => void triggerRun()}>
            Run Daily Scan
          </button>
        </div>
      </header>

      <section className="disclaimer">
        <strong>Investment Disclaimer:</strong> Informational research only. Verify zoning, legal access, title,
        liens, flood status, and utility feasibility before acting.
      </section>

      {runState && <section className="status">{runState}</section>}
      {error && <section className="error">{error}</section>}

      {loading ? (
        <section className="card">Loading...</section>
      ) : (
        <>
          <section className="kpi-grid">
            <article className="kpi-card">
              <span>Total Candidates</span>
              <strong>{kpis.total}</strong>
            </article>
            <article className="kpi-card">
              <span>Average Score</span>
              <strong>{kpis.avgScore.toFixed(1)}</strong>
            </article>
            <article className="kpi-card">
              <span>Under $4k</span>
              <strong>{kpis.under4k}</strong>
            </article>
            <article className="kpi-card">
              <span>Mode</span>
              <strong>{settings?.mock_mode ? "Mock" : "Live"}</strong>
            </article>
          </section>

          <section className="provider-strip card">
            <h2>Provider Health</h2>
            <div className="provider-meta">
              <span>RapidAPI: {settings?.rapidapi_configured ? "Configured" : "Missing Key/Host"}</span>
              <span>Regrid: {settings?.regrid_configured ? "Configured" : "Missing Key"}</span>
              <span>Listing Slug: {settings?.rapidapi_provider_slug ?? "n/a"}</span>
              <span>Metrics Slug: {settings?.rapidapi_metrics_slug ?? "n/a"}</span>
              <span>Auction Source: {settings?.auction_source_mode ?? "n/a"}</span>
              <span>CSV Dir: {settings?.auction_csv_dir ?? "n/a"}</span>
              <span>CSV Glob: {settings?.auction_csv_glob ?? "n/a"}</span>
              <span>CSV Age Days: {settings?.auction_max_file_age_days ?? 0}</span>
              <span>Metrics Cache Days: {settings?.market_metrics_cache_lookback_days ?? 0}</span>
              <span>
                Personalization:{" "}
                {settings?.personalization_ready
                  ? `Ready (${settings?.feedback_labels_count ?? 0}/${settings?.personalization_threshold ?? 50})`
                  : `Not Ready (${settings?.feedback_labels_count ?? 0}/${settings?.personalization_threshold ?? 50})`}
              </span>
            </div>
            {providerHealth.length === 0 ? (
              <p>No provider events yet.</p>
            ) : (
              <ul className="provider-list">
                {providerHealth.map((event: ProviderEventStatus) => (
                  <li key={`${event.provider}-${event.created_at}`}>
                    <strong>{event.provider}</strong>
                    <span className={`pill-${event.status}`}>{event.status}</span>
                    <small>{new Date(event.created_at).toLocaleString()}</small>
                    {event.error_summary && <em>{event.error_summary}</em>}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <nav className="tabs">
            <button
              className={activeTab === "dashboard" ? "active" : ""}
              onClick={() => setActiveTab("dashboard")}
            >
              Dashboard
            </button>
            <button className={activeTab === "digest" ? "active" : ""} onClick={() => setActiveTab("digest")}>
              Digest
            </button>
            <button className={activeTab === "runs" ? "active" : ""} onClick={() => setActiveTab("runs")}>
              Runs
            </button>
          </nav>

          {activeTab === "dashboard" && (
            <section className="dashboard-grid">
              <article className="card">
                <h2>Top Opportunities</h2>
                <section className="filters">
                  <label>
                    County
                    <input
                      value={filterCounty}
                      onChange={(event) => setFilterCounty(event.target.value)}
                      placeholder="e.g. Travis"
                    />
                  </label>
                  <label>
                    Min Score
                    <input
                      value={filterMinScore}
                      onChange={(event) => setFilterMinScore(event.target.value)}
                      type="number"
                      min={0}
                      max={100}
                      placeholder="0-100"
                    />
                    {filterErrors.minScore && <small className="field-error">{filterErrors.minScore}</small>}
                  </label>
                  <label>
                    Max Price
                    <input
                      value={filterMaxPrice}
                      onChange={(event) => setFilterMaxPrice(event.target.value)}
                      type="number"
                      min={0}
                      step={100}
                    />
                    {filterErrors.maxPrice ? (
                      <small className="field-error">{filterErrors.maxPrice}</small>
                    ) : (
                      <small className="field-hint">USD amount, e.g. 5000</small>
                    )}
                  </label>
                  <div className="filter-actions">
                    <button className="primary" onClick={applyFilters} disabled={!canApplyFilters}>
                      Apply
                    </button>
                    <button onClick={resetFilters}>Reset</button>
                  </div>
                </section>
                <table>
                  <thead>
                    <tr>
                      <th>County</th>
                      <th>Price</th>
                      <th>Acres</th>
                      <th>Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {opportunities.length === 0 ? (
                      <tr>
                        <td colSpan={4}>No opportunities matched your filters.</td>
                      </tr>
                    ) : (
                      opportunities.map((item) => (
                        <tr key={item.id} onClick={() => void selectOpportunity(item.id)}>
                          <td>{item.county}</td>
                          <td>{currency(item.price)}</td>
                          <td>{item.acreage.toFixed(2)}</td>
                          <td>
                            <span className={`score-pill ${scoreClass(item.final_score)}`}>{item.final_score}</span>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
                <div className="pagination">
                  <button onClick={() => goToPage(query.page - 1)} disabled={query.page <= 1}>
                    Prev
                  </button>
                  <span>
                    Page {query.page} of {totalPages} · Total {opportunityTotal}
                  </span>
                  <button onClick={() => goToPage(query.page + 1)} disabled={query.page >= totalPages}>
                    Next
                  </button>
                  <label>
                    Page Size
                    <select
                      value={query.pageSize}
                      onChange={(event) => updatePageSize(Number.parseInt(event.target.value, 10))}
                    >
                      <option value={10}>10</option>
                      <option value={25}>25</option>
                      <option value={50}>50</option>
                    </select>
                  </label>
                </div>
              </article>

              <article className="card">
                <h2>Opportunity Detail</h2>
                {!selected ? (
                  <p>Select a row to inspect scoring details.</p>
                ) : (
                  <div className="detail">
                    <h3>
                      {selected.county}, {selected.state}
                    </h3>
                    <p>
                      {currency(selected.price)} · {selected.acreage.toFixed(2)} acres · {selected.source_type}
                    </p>
                    <div className="score-line">
                      <span>Final Score</span>
                      <strong className={scoreClass(selected.score_breakdown.final_score)}>
                        {selected.score_breakdown.final_score.toFixed(2)}
                      </strong>
                    </div>
                    <div className="score-line">
                      <span>Personalization Score</span>
                      <strong>
                        {selected.score_breakdown.personalization_score === null
                          ? "n/a"
                          : selected.score_breakdown.personalization_score.toFixed(2)}
                      </strong>
                    </div>
                    <p>
                      Model: {selected.model_version ?? "base-only"} · Blend Weight: {selected.blend_weight.toFixed(2)}
                    </p>
                    <ul className="reason-list">
                      {selected.reason_codes.map((reason) => (
                        <li key={reason.code}>
                          <span>{reason.label}</span>
                          <strong>{reason.impact.toFixed(1)}</strong>
                        </li>
                      ))}
                      {selected.caution_code && (
                        <li className="caution">
                          <span>{selected.caution_code.label}</span>
                          <strong>{selected.caution_code.impact.toFixed(1)}</strong>
                        </li>
                      )}
                    </ul>

                    <div className="feedback">
                      <button onClick={() => void submitVote("up")}>Thumbs Up</button>
                      <button onClick={() => void submitVote("down")}>Thumbs Down</button>
                    </div>
                  </div>
                )}
              </article>
            </section>
          )}

          {activeTab === "digest" && (
            <section className="card">
              <h2>Daily Digest</h2>
              {latestDigest ? (
                <p>
                  Latest ({new Date(latestDigest.generated_at).toLocaleString()}): {latestDigest.summary}
                </p>
              ) : (
                <p>No digest available.</p>
              )}
              <h3>History</h3>
              <ul className="list">
                {digests.map((digest) => (
                  <li key={digest.id}>
                    <span>{new Date(digest.generated_at).toLocaleString()}</span>
                    <small>{digest.summary}</small>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {activeTab === "runs" && (
            <section className="card">
              <h2>Pipeline Runs</h2>
              <ul className="list">
                {runs.map((run) => (
                  <li key={run.id}>
                    <span>
                      {run.status.toUpperCase()} · {new Date(run.started_at).toLocaleString()}
                    </span>
                    <small>
                      Listings: {run.listings_ingested}, Auctions: {run.auctions_ingested}, Scored:{" "}
                      {run.candidates_scored}, Excluded: {run.excluded_count}
                    </small>
                    {run.provider_events.length > 0 && (
                      <small>
                        Providers:{" "}
                        {run.provider_events
                          .map((event) => `${event.provider}:${event.status}`)
                          .join(" | ")}
                      </small>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}
