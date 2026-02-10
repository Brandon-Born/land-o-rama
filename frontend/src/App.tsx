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

export default function App() {
  const [opportunities, setOpportunities] = useState<OpportunityListItem[]>([]);
  const [selected, setSelected] = useState<OpportunityDetail | null>(null);
  const [latestDigest, setLatestDigest] = useState<DigestSummary | null>(null);
  const [digests, setDigests] = useState<DigestSummary[]>([]);
  const [runs, setRuns] = useState<RunStatus[]>([]);
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"dashboard" | "digest" | "runs">("dashboard");
  const [runState, setRunState] = useState<string>("");

  async function loadAll() {
    setLoading(true);
    setError(null);
    try {
      const [opportunitiesResponse, latestDigestResponse, digestsResponse, runsResponse, settingsResponse] =
        await Promise.all([fetchOpportunities(), fetchLatestDigest(), fetchDigests(), fetchRuns(), fetchSettings()]);
      setOpportunities(opportunitiesResponse.items);
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
    void loadAll();
  }, []);

  const kpis = useMemo(() => {
    const total = opportunities.length;
    const avgScore =
      total > 0 ? opportunities.reduce((sum, item) => sum + item.final_score, 0) / total : 0;
    const under4k = opportunities.filter((item) => item.price < 4000).length;
    return { total, avgScore, under4k };
  }, [opportunities]);

  const providerHealth = useMemo(() => settings?.provider_health ?? [], [settings]);

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
      await loadAll();
    } catch (runError) {
      setError((runError as Error).message);
      setRunState("Run failed");
    }
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <h1>Land-O-Rama</h1>
          <p>Texas sub-$5k land scanner with 5-year upside scoring and strict risk exclusions.</p>
        </div>
        <div className="controls">
          <button onClick={() => void loadAll()}>Refresh</button>
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
              <span>Slug: {settings?.rapidapi_provider_slug ?? "n/a"}</span>
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
                    {opportunities.map((item) => (
                      <tr key={item.id} onClick={() => void selectOpportunity(item.id)}>
                        <td>{item.county}</td>
                        <td>{currency(item.price)}</td>
                        <td>{item.acreage.toFixed(2)}</td>
                        <td>
                          <span className={`score-pill ${scoreClass(item.final_score)}`}>{item.final_score}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
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
