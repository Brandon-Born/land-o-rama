import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import App from "./App";
import { installFetchMock } from "./test/mockFetch";

type OpportunityItem = {
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

const allItems: OpportunityItem[] = Array.from({ length: 30 }, (_, idx) => {
  const index = idx + 1;
  return {
    id: `opp-${index}`,
    county: index % 2 === 0 ? "Bell" : "Travis",
    state: "TX",
    price: 1500 + index * 100,
    acreage: 0.2 + index * 0.01,
    final_score: 95 - index,
    base_score: 95 - index,
    source_type: index % 3 === 0 ? "auction" : "listing",
    created_at: "2026-02-10T00:00:00Z",
  };
});

function detailFor(id: string) {
  const item = allItems.find((candidate) => candidate.id === id) ?? allItems[0];
  const hasDirectUrl = item.id !== "opp-3";
  return {
    id: item.id,
    parcel_id: `parcel-${item.id}`,
    county: item.county,
    state: item.state,
    price: item.price,
    acreage: item.acreage,
    source_type: item.source_type,
    source_id: item.id,
    source_name: item.source_type === "auction" ? "County Auction Feed" : "RapidAPI Listing Feed",
    source_url: hasDirectUrl ? `https://example.test/opportunity/${item.id}` : null,
    is_excluded: false,
    exclusion_reason: null,
    reason_codes: [
      { code: "ACCESSIBILITY", label: "Accessibility", direction: "positive", impact: 90 },
      { code: "MARKET_GROWTH", label: "Market Growth", direction: "positive", impact: 85 },
      { code: "LOW_RISK_PROFILE", label: "Low Risk Profile", direction: "positive", impact: 80 },
    ],
    caution_code: { code: "RISK_BURDEN", label: "Risk Burden", direction: "caution", impact: 20 },
    score_breakdown: {
      market_growth_score: 85,
      development_pressure_score: 78,
      accessibility_score: 90,
      liquidity_score: 70,
      risk_penalty_score: 20,
      base_score: item.base_score,
      final_score: item.final_score,
      personalization_score: null,
    },
    model_version: null,
    blend_weight: 0.15,
    created_at: item.created_at,
  };
}

function opportunitiesBody(url: URL) {
  const county = (url.searchParams.get("county") ?? "").toLowerCase();
  const minScoreRaw = url.searchParams.get("min_score");
  const maxPriceRaw = url.searchParams.get("max_price");
  const page = Number.parseInt(url.searchParams.get("page") ?? "1", 10);
  const pageSize = Number.parseInt(url.searchParams.get("page_size") ?? "25", 10);
  const minScore = minScoreRaw ? Number(minScoreRaw) : null;
  const maxPrice = maxPriceRaw ? Number(maxPriceRaw) : 5000;

  let filtered = allItems.filter((item) => item.price <= maxPrice);
  if (county) filtered = filtered.filter((item) => item.county.toLowerCase() === county);
  if (minScore !== null && Number.isFinite(minScore)) filtered = filtered.filter((item) => item.final_score >= minScore);

  const total = filtered.length;
  const start = (Math.max(page, 1) - 1) * Math.max(pageSize, 1);
  const pageItems = filtered.slice(start, start + Math.max(pageSize, 1));
  return {
    items: pageItems,
    total,
    page,
    page_size: pageSize,
    generated_at: "2026-02-10T00:00:00Z",
  };
}

function defaultHandler(url: URL, init?: RequestInit): { status?: number; body: unknown } {
  if (url.pathname.endsWith("/opportunities") && init?.method !== "POST") {
    return { body: opportunitiesBody(url) };
  }
  if (url.pathname.includes("/opportunities/") && !url.pathname.endsWith("/feedback")) {
    const id = url.pathname.split("/").pop() ?? "opp-1";
    return { body: detailFor(id) };
  }
  if (url.pathname.endsWith("/feedback")) {
    return { body: { status: "ok", feedback_id: "fb-1" } };
  }
  if (url.pathname.endsWith("/digests/latest")) {
    return { body: { id: "digest-1", generated_at: "2026-02-10T00:00:00Z", summary: "digest", opportunity_ids: ["opp-1"] } };
  }
  if (url.pathname.endsWith("/digests")) {
    return { body: { items: [{ id: "digest-1", generated_at: "2026-02-10T00:00:00Z", summary: "digest", opportunity_ids: ["opp-1"] }] } };
  }
  if (url.pathname.endsWith("/runs")) {
    return {
      body: {
        items: [
          {
            id: "run-1",
            run_type: "daily",
            status: "success",
            started_at: "2026-02-10T00:00:00Z",
            finished_at: "2026-02-10T00:01:00Z",
            listings_ingested: 10,
            auctions_ingested: 4,
            candidates_scored: 14,
            excluded_count: 2,
            error_summary: null,
            provider_events: [{ provider: "county_auction_scraper", status: "success", error_summary: null, created_at: "2026-02-10T00:01:00Z" }],
          },
        ],
      },
    };
  }
  if (url.pathname.endsWith("/settings")) {
    return {
      body: {
        state: "TX",
        refresh_time: "08:00",
        mock_mode: true,
        disclaimers_enabled: true,
        regrid_configured: false,
        price_cap: 6000,
        auction_source_mode: "mock",
        auction_csv_dir: "/Users/bborn/land-o-rama/data/auction_feeds",
        auction_csv_glob: "*.csv",
        auction_max_file_age_days: 14,
        provider_timeout_seconds: 12,
        provider_max_retries: 2,
        market_metrics_cache_lookback_days: 30,
        scraper_primary_source: "county_auction_scraper",
        scraper_mode: "download_first",
        scraper_target_counties: ["Hunt County, TX"],
        scraper_last_success_at: null,
        scraper_last_success_county: null,
        scraper_parse_error_count: 0,
        scraper_last_records_accepted: 0,
        personalization_ready: false,
        feedback_labels_count: 0,
        personalization_threshold: 50,
        personalization_blend_weight: 0.15,
        provider_health: [{ provider: "county_auction_scraper", status: "success", error_summary: null, created_at: "2026-02-10T00:01:00Z" }],
      },
    };
  }
  if (url.pathname.endsWith("/jobs/run-daily")) {
    return { body: { run_id: "run-new", status: "success" } };
  }
  return { status: 404, body: { error: "not found" } };
}

function opportunitiesCalls(calls: URL[]): URL[] {
  return calls.filter((url) => url.pathname.endsWith("/opportunities"));
}

async function waitForOpportunitiesLoaded(calls: URL[]) {
  await screen.findByRole("heading", { name: "Top Opportunities" });
  await waitFor(() => {
    expect(opportunitiesCalls(calls).length).toBeGreaterThan(0);
  });
}

beforeEach(() => {
  window.history.replaceState(null, "", "/");
});

it("loads with default opportunities query params", async () => {
  const { calls } = installFetchMock(defaultHandler);
  render(<App />);

  await waitForOpportunitiesLoaded(calls);
  const firstCall = opportunitiesCalls(calls)[0];
  expect(firstCall.searchParams.get("page")).toBe("1");
  expect(firstCall.searchParams.get("page_size")).toBe("25");
  expect(firstCall.searchParams.get("max_price")).toBe("5000");
});

it("applies filters and sends mapped query params", async () => {
  const user = userEvent.setup();
  const { calls } = installFetchMock(defaultHandler);
  render(<App />);
  await waitForOpportunitiesLoaded(calls);

  await user.clear(screen.getByLabelText(/County/i));
  await user.type(screen.getByLabelText(/County/i), "bell");
  await user.clear(screen.getByLabelText(/Min Score/i));
  await user.type(screen.getByLabelText(/Min Score/i), "80");
  await user.clear(screen.getByLabelText(/Max Price/i));
  await user.type(screen.getByLabelText(/Max Price/i), "3000");
  await user.click(screen.getByRole("button", { name: "Apply" }));

  await waitFor(() => {
    const lastCall = opportunitiesCalls(calls).at(-1);
    expect(lastCall?.searchParams.get("county")).toBe("bell");
    expect(lastCall?.searchParams.get("min_score")).toBe("80");
    expect(lastCall?.searchParams.get("max_price")).toBe("3000");
    expect(lastCall?.searchParams.get("page")).toBe("1");
  });
});

it("resets filters to defaults", async () => {
  const user = userEvent.setup();
  const { calls } = installFetchMock(defaultHandler);
  render(<App />);
  await waitForOpportunitiesLoaded(calls);

  await user.type(screen.getByLabelText(/County/i), "bell");
  await user.type(screen.getByLabelText(/Min Score/i), "70");
  await user.clear(screen.getByLabelText(/Max Price/i));
  await user.type(screen.getByLabelText(/Max Price/i), "2700");
  await user.click(screen.getByRole("button", { name: "Reset" }));

  await waitFor(() => {
    const lastCall = opportunitiesCalls(calls).at(-1);
    expect(lastCall?.searchParams.get("county")).toBeNull();
    expect(lastCall?.searchParams.get("min_score")).toBeNull();
    expect(lastCall?.searchParams.get("max_price")).toBe("5000");
  });
  expect((screen.getByLabelText(/County/i) as HTMLInputElement).value).toBe("");
  expect((screen.getByLabelText(/Min Score/i) as HTMLInputElement).value).toBe("");
  expect((screen.getByLabelText(/Max Price/i) as HTMLInputElement).value).toBe("5000");
});

it("supports next/prev paging and page-size changes", async () => {
  const user = userEvent.setup();
  const { calls } = installFetchMock(defaultHandler);
  render(<App />);
  await waitForOpportunitiesLoaded(calls);

  await user.click(screen.getByRole("button", { name: "Next" }));
  await waitFor(() => {
    const lastCall = opportunitiesCalls(calls).at(-1);
    expect(lastCall?.searchParams.get("page")).toBe("2");
    expect(lastCall?.searchParams.get("page_size")).toBe("25");
  });

  await user.selectOptions(screen.getByLabelText(/Page Size/i), "50");
  await waitFor(() => {
    const lastCall = opportunitiesCalls(calls).at(-1);
    expect(lastCall?.searchParams.get("page")).toBe("1");
    expect(lastCall?.searchParams.get("page_size")).toBe("50");
  });
});

it("hydrates query state from URL on first load", async () => {
  window.history.replaceState(null, "", "/?county=bell&minScore=60&maxPrice=2900&page=2&pageSize=10&tab=digest");
  const { calls } = installFetchMock(defaultHandler);
  render(<App />);

  await screen.findByText("Daily Digest");
  const firstCall = opportunitiesCalls(calls)[0];
  expect(firstCall.searchParams.get("county")).toBe("bell");
  expect(firstCall.searchParams.get("min_score")).toBe("60");
  expect(firstCall.searchParams.get("max_price")).toBe("2900");
  expect(firstCall.searchParams.get("page")).toBe("2");
  expect(firstCall.searchParams.get("page_size")).toBe("10");
});

it("hydrates opportunity tab from URL and requests selected detail", async () => {
  window.history.replaceState(null, "", "/?tab=opportunity&opportunityId=opp-5");
  const { calls } = installFetchMock(defaultHandler);
  render(<App />);

  await screen.findByRole("heading", { name: "Opportunity Detail" });
  await waitFor(() => {
    const detailCall = calls.find((url) => url.pathname.endsWith("/opportunities/opp-5"));
    expect(detailCall).toBeDefined();
  });
});

it("loads detail when selecting a row", async () => {
  const user = userEvent.setup();
  const { calls } = installFetchMock(defaultHandler);
  render(<App />);
  await waitForOpportunitiesLoaded(calls);

  const rows = screen.getAllByRole("row");
  await user.click(rows[2]);
  await screen.findByRole("heading", { name: "Opportunity Detail" });
  await waitFor(() => {
    const detailCall = calls.find((url) => url.pathname.endsWith("/opportunities/opp-2"));
    expect(detailCall).toBeDefined();
  });
});

it("renders error banner when opportunities request fails", async () => {
  installFetchMock((url, init) => {
    if (url.pathname.endsWith("/opportunities") && init?.method !== "POST") {
      return { status: 500, body: { error: "boom" } };
    }
    return defaultHandler(url, init);
  });
  render(<App />);
  expect(await screen.findByText(/boom/i)).toBeInTheDocument();
});

it("renders provider health configuration and events", async () => {
  const user = userEvent.setup();
  installFetchMock((url, init) => {
    if (url.pathname.endsWith("/settings")) {
      return {
        body: {
          state: "TX",
          refresh_time: "08:00",
          mock_mode: false,
          disclaimers_enabled: true,
          regrid_configured: false,
          price_cap: 6000,
          auction_source_mode: "csv",
          auction_csv_dir: "/tmp/auctions",
          auction_csv_glob: "*.csv",
          auction_max_file_age_days: 10,
          provider_timeout_seconds: 12,
          provider_max_retries: 2,
          market_metrics_cache_lookback_days: 30,
          scraper_primary_source: "county_auction_scraper",
          scraper_mode: "download_first",
          scraper_target_counties: ["Hunt County, TX"],
          scraper_last_success_at: "2026-02-10T00:02:00Z",
          scraper_last_success_county: "Hunt",
          scraper_parse_error_count: 2,
          scraper_last_records_accepted: 11,
          personalization_ready: true,
          feedback_labels_count: 75,
          personalization_threshold: 50,
          personalization_blend_weight: 0.15,
          provider_health: [
            { provider: "county_auction_scraper", status: "degraded", error_summary: "provider timeout", created_at: "2026-02-10T00:01:00Z" },
            { provider: "regrid_enrichment", status: "failed", error_summary: "missing api key", created_at: "2026-02-10T00:01:30Z" },
          ],
        },
      };
    }
    return defaultHandler(url, init);
  });

  render(<App />);
  await screen.findByRole("heading", { name: "Top Opportunities" });
  await user.click(screen.getByRole("button", { name: "Runs" }));
  await waitFor(() => {
    expect(screen.getByText("Primary Source: county_auction_scraper")).toBeInTheDocument();
    expect(screen.getByText("Scraper Mode: download_first")).toBeInTheDocument();
    expect(screen.getByText("Target Counties: Hunt County, TX")).toBeInTheDocument();
    expect(screen.getByText("Last Accepted Records: 11")).toBeInTheDocument();
    expect(screen.getByText("Last Parse Errors: 2")).toBeInTheDocument();
    expect(screen.getByText("Regrid: Missing Key")).toBeInTheDocument();
    expect(screen.getByText("Auction Source: csv")).toBeInTheDocument();
    expect(screen.getByText(/Personalization: Ready/i)).toBeInTheDocument();
    expect(screen.getByText("provider timeout")).toBeInTheDocument();
    expect(screen.getByText("missing api key")).toBeInTheDocument();
  });
});

it("shows source destination link when available", async () => {
  const user = userEvent.setup();
  const { calls } = installFetchMock(defaultHandler);
  render(<App />);
  await waitForOpportunitiesLoaded(calls);

  const rows = screen.getAllByRole("row");
  await user.click(rows[1]);
  const link = await screen.findByRole("link", { name: "Open Source Listing" });
  expect(link).toHaveAttribute("href", "https://example.test/opportunity/opp-1");
});

it("shows manual lookup fallback when source URL is unavailable", async () => {
  const user = userEvent.setup();
  const { calls } = installFetchMock(defaultHandler);
  render(<App />);
  await waitForOpportunitiesLoaded(calls);

  const rows = screen.getAllByRole("row");
  await user.click(rows[3]);
  expect(await screen.findByText(/No direct source URL was captured/i)).toBeInTheDocument();
  expect(screen.getByText(/source ID/i)).toBeInTheDocument();
});

it("renders runs tab with degraded run provider summary", async () => {
  const user = userEvent.setup();
  installFetchMock((url, init) => {
    if (url.pathname.endsWith("/runs")) {
      return {
        body: {
          items: [
            {
              id: "run-2",
              run_type: "daily",
              status: "degraded",
              started_at: "2026-02-10T00:10:00Z",
              finished_at: "2026-02-10T00:11:00Z",
              listings_ingested: 6,
              auctions_ingested: 3,
              candidates_scored: 9,
              excluded_count: 1,
              error_summary: "listing source degraded",
              provider_events: [
                { provider: "county_auction_scraper", status: "failed", error_summary: "timeout", created_at: "2026-02-10T00:10:30Z" },
                { provider: "scraper_no_new_data", status: "degraded", error_summary: null, created_at: "2026-02-10T00:10:31Z" },
              ],
            },
          ],
        },
      };
    }
    return defaultHandler(url, init);
  });

  render(<App />);
  await screen.findByRole("heading", { name: "Top Opportunities" });
  await user.click(screen.getByRole("button", { name: "Runs" }));

  expect(await screen.findByText(/^DEGRADED\s·/i)).toBeInTheDocument();
  expect(screen.getByText(/Providers: county_auction_scraper:failed \| scraper_no_new_data:degraded/)).toBeInTheDocument();
});

it("blocks apply when min score is out of range and allows after fix", async () => {
  const user = userEvent.setup();
  const { calls } = installFetchMock(defaultHandler);
  render(<App />);
  await waitForOpportunitiesLoaded(calls);

  const applyButton = screen.getByRole("button", { name: "Apply" });
  const beforeInvalidAttempt = opportunitiesCalls(calls).length;
  await user.clear(screen.getByLabelText(/Min Score/i));
  await user.type(screen.getByLabelText(/Min Score/i), "101");
  await waitFor(() => {
    expect(screen.getByText("Min score must be between 0 and 100.")).toBeInTheDocument();
  });
  expect(applyButton).toBeDisabled();

  await user.click(applyButton);
  await waitFor(() => {
    expect(opportunitiesCalls(calls).length).toBe(beforeInvalidAttempt);
  });

  await user.clear(screen.getByLabelText(/Min Score/i));
  await user.type(screen.getByLabelText(/Min Score/i), "90");
  await waitFor(() => {
    expect(screen.queryByText("Min score must be between 0 and 100.")).not.toBeInTheDocument();
    expect(applyButton).toBeEnabled();
  });

  await user.click(applyButton);
  await waitFor(() => {
    const lastCall = opportunitiesCalls(calls).at(-1);
    expect(lastCall?.searchParams.get("min_score")).toBe("90");
  });
});

it("blocks apply for invalid max price and reset clears validation", async () => {
  const user = userEvent.setup();
  const { calls } = installFetchMock(defaultHandler);
  render(<App />);
  await waitForOpportunitiesLoaded(calls);

  const applyButton = screen.getByRole("button", { name: "Apply" });
  await user.clear(screen.getByLabelText(/Max Price/i));
  await user.type(screen.getByLabelText(/Max Price/i), "0");
  await waitFor(() => {
    expect(screen.getByText("Max price must be greater than 0.")).toBeInTheDocument();
  });
  expect(applyButton).toBeDisabled();

  await user.click(screen.getByRole("button", { name: "Reset" }));
  await waitFor(() => {
    expect(screen.queryByText("Max price must be greater than 0.")).not.toBeInTheDocument();
    expect(applyButton).toBeEnabled();
  });
});
