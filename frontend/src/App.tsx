import { useState, useEffect, useCallback } from "react";
import BenchmarkList from "./components/BenchmarkList";
import BenchmarkDetail from "./components/BenchmarkDetail";
import BenchmarkCompare from "./components/BenchmarkCompare";
import TestResultsView from "./components/TestResultsView";
import StatsView from "./components/StatsView";
import TestNav from "./components/TestNav";
import AuthModal from "./components/AuthModal";
import { useAuth } from "./context/AuthContext";
import { Benchmark, BenchmarkStat } from "./types";
import axios from "axios";

// URL hash routing helpers
function parseHash(): { view: string; id?: string; ids?: string[]; test?: string; tab?: number } {
  const hash = window.location.hash.slice(1); // remove #
  if (!hash) return { view: "list" };

  const [path, ...rest] = hash.split("/");
  const param = rest.join("/");

  switch (path) {
    case "run":
      return { view: "detail", id: param };
    case "compare":
      return { view: "compare", ids: param.split(",") };
    case "test":
      return { view: "test-results", test: param };
    case "stats":
      return { view: "stats", test: param };
    case "top":
      return { view: "list", tab: parseInt(param) || 0 };
    default:
      return { view: "list" };
  }
}

function buildHash(view: string, params?: { id?: number; ids?: number[]; test?: string; tab?: number }): string {
  switch (view) {
    case "detail":
      return `#run/${params?.id}`;
    case "compare":
      return `#compare/${params?.ids?.join(",")}`;
    case "test-results":
      return `#test/${params?.test}`;
    case "stats":
      return `#stats/${params?.test}`;
    case "list":
      if (params?.tab !== undefined && params.tab > 0) {
        return `#top/${params.tab}`;
      }
      return "";
    default:
      return "";
  }
}

// API_URL for fetch requests (empty = relative path, works with reverse proxy)
const API_URL = import.meta.env.VITE_API_URL || "";

// Display URL for curl commands (shows the actual server URL)
const DISPLAY_URL = import.meta.env.VITE_API_URL || window.location.origin;


type View = "list" | "detail" | "compare" | "test-results" | "stats";

function App() {
  const { user, logout, isLoading: authLoading } = useAuth();
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [showRunOptions, setShowRunOptions] = useState(false);
  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
  const [leaderboard, setLeaderboard] = useState<BenchmarkStat[]>([]);
  const [leaderboardTab, setLeaderboardTab] = useState(0);
  const [view, setView] = useState<View>("list");
  const [urlInitialized, setUrlInitialized] = useState(false);

  // Leaderboard tab configurations
  const leaderboardTabs = [
    { label: "CPU MT (system)", test: "passmark_cpu_mt", groupBy: "system" },
    { label: "CPU MT (CPU)", test: "passmark_cpu_mt", groupBy: "cpu" },
    { label: "CPU ST (system)", test: "passmark_cpu_single", groupBy: "system" },
    { label: "CPU ST (CPU)", test: "passmark_cpu_single", groupBy: "cpu" },
    { label: "Memory (system)", test: "passmark_memory", groupBy: "system" },
    { label: "AES256 (CPU)", test: "openssl_aes256", groupBy: "cpu" },
    { label: "SHA256 (CPU)", test: "openssl_sha256", groupBy: "cpu" },
    { label: "Sysbench ST (CPU)", test: "sysbench_cpu_st", groupBy: "cpu" },
    { label: "Sysbench MT (CPU)", test: "sysbench_cpu_mt", groupBy: "cpu" },
    { label: "Pi Calc (CPU)", test: "pi_calculation", groupBy: "cpu" },
    { label: "Disk Write (system)", test: "disk_write", groupBy: "system" },
  ];
  const [selectedBenchmark, setSelectedBenchmark] = useState<number | null>(
    null
  );
  const [selectedTest, setSelectedTest] = useState<string | null>(null);
  const [selectedForCompare, setSelectedForCompare] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const formatLeaderboardValue = (value: number | null | undefined, unit: string | null | undefined) => {
    if (value === null || value === undefined) return "—";
    // Show 2 decimal places for time-based units (seconds)
    const u = unit?.toLowerCase() ?? "";
    if (u.includes("second") || u === "s" || u === "ns") {
      return value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    // No decimals for large scores
    return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
  };

  // Update URL when state changes
  const updateUrl = useCallback((newView: View, params?: { id?: number; ids?: number[]; test?: string; tab?: number }) => {
    const hash = buildHash(newView, params);
    if (window.location.hash !== hash) {
      window.history.pushState(null, "", hash || window.location.pathname);
    }
  }, []);

  // Initialize state from URL on mount
  useEffect(() => {
    const initFromUrl = () => {
      const parsed = parseHash();
      if (parsed.view === "detail" && parsed.id) {
        setSelectedBenchmark(parseInt(parsed.id));
        setView("detail");
      } else if (parsed.view === "compare" && parsed.ids?.length) {
        setSelectedForCompare(parsed.ids.map(id => parseInt(id)));
        setView("compare");
      } else if (parsed.view === "test-results" && parsed.test) {
        setSelectedTest(parsed.test);
        setView("test-results");
      } else if (parsed.view === "stats" && parsed.test) {
        setSelectedTest(parsed.test);
        setView("stats");
      } else if (parsed.tab !== undefined) {
        setLeaderboardTab(parsed.tab);
      }
      setUrlInitialized(true);
    };

    initFromUrl();

    // Handle browser back/forward
    const handlePopState = () => {
      initFromUrl();
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  useEffect(() => {
    fetchBenchmarks();
  }, []);

  useEffect(() => {
    fetchLeaderboard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [leaderboardTab]);

  const fetchBenchmarks = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await axios.get(`${API_URL}/api/v1/benchmarks?limit=10`);
      setBenchmarks(response.data);
    } catch (err) {
      setError("Failed to fetch benchmarks");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchLeaderboard = async () => {
    try {
      const tab = leaderboardTabs[leaderboardTab];
      const response = await axios.get(
        `${API_URL}/api/v1/stats/by-test?test_name=${tab.test}&group_by=${tab.groupBy}&limit=10`
      );
      setLeaderboard(response.data);
    } catch (err) {
      console.error("Failed to fetch leaderboard:", err);
    }
  };

  const handleSelect = (id: number) => {
    setSelectedBenchmark(id);
    setView("detail");
    updateUrl("detail", { id });
  };

  const handleSelectTest = (testName: string) => {
    setSelectedTest(testName);
    setView("test-results");
    updateUrl("test-results", { test: testName });
  };

  const handleSelectStats = (testName: string) => {
    setSelectedTest(testName);
    setView("stats");
    updateUrl("stats", { test: testName });
  };

  const handleToggleCompare = (id: number) => {
    setSelectedForCompare((prev) =>
      prev.includes(id)
        ? prev.filter((x) => x !== id)
        : prev.length < 4
          ? [...prev, id]
          : prev
    );
  };

  const handleCompare = () => {
    if (selectedForCompare.length >= 2) {
      setView("compare");
      updateUrl("compare", { ids: selectedForCompare });
    }
  };

  const handleCompareFromTest = (runIds: number[]) => {
    setSelectedForCompare(runIds);
    setView("compare");
    updateUrl("compare", { ids: runIds });
  };

  const handleBack = () => {
    setView("list");
    setSelectedBenchmark(null);
    setSelectedTest(null);
    updateUrl("list");
  };

  const clearSelection = () => {
    setSelectedForCompare([]);
  };

  const goHome = () => {
    setView("list");
    setSelectedBenchmark(null);
    setSelectedTest(null);
    updateUrl("list");
  };

  // Update URL when leaderboard tab changes (only after initial load)
  const handleLeaderboardTabChange = (idx: number) => {
    setLeaderboardTab(idx);
    if (urlInitialized) {
      updateUrl("list", { tab: idx });
    }
  };

  return (
    <div className="app">
      <header className="header">
        <img src="/benchcom.svg" alt="BENCHCOM" className="logo clickable" onClick={goHome} />
        <div className="auth-section">
          <a
            href="https://github.com/mkoskinen/benchcom/blob/main/docs/ABOUT.md"
            target="_blank"
            rel="noopener noreferrer"
            className="about-link"
          >
            About & Help
          </a>
          <span className="auth-separator">|</span>
          {authLoading ? null : user ? (
            <div className="auth-user">
              <span className="auth-username">{user.username}{user.is_admin && " (admin)"}</span>
              <span className="auth-link" onClick={logout}>
                Logout
              </span>
            </div>
          ) : (
            <span className="auth-link" onClick={() => setShowAuthModal(true)}>
              Login / Register
            </span>
          )}
        </div>
        <a
          href="https://github.com/mkoskinen/benchcom"
          target="_blank"
          rel="noopener noreferrer"
          className="github-link"
        >
          <img src="/github-mark.svg" alt="GitHub" className="github-icon" />
        </a>
      </header>

      {showAuthModal && <AuthModal onClose={() => setShowAuthModal(false)} />}

      <div className="run-section">
        <div className="curl-command">
          <code
            className="curl-code"
            onClick={() => copyToClipboard(
              `curl -sL https://raw.githubusercontent.com/mkoskinen/benchcom/main/benchcom.sh | bash -s -- -u ${DISPLAY_URL}`
            )}
            title="Click to copy"
          >
            curl -sL https://raw.githubusercontent.com/mkoskinen/benchcom/main/benchcom.sh | bash -s -- -u {DISPLAY_URL}
          </code>
          <span
            className="expand-toggle"
            onClick={() => setShowRunOptions(!showRunOptions)}
          >
            {showRunOptions ? "[-]" : "[+] options"}
          </span>
        </div>

        {showRunOptions && (
          <div className="run-options">
            <div className="run-option">
              <div className="run-option-label">Quick mode (OpenSSL only):</div>
              <code
                className="curl-code"
                onClick={() => copyToClipboard(
                  `curl -sL https://raw.githubusercontent.com/mkoskinen/benchcom/main/benchcom.sh | bash -s -- --api-url ${DISPLAY_URL} --fast`
                )}
                title="Click to copy"
              >
                ... | bash -s -- --api-url {DISPLAY_URL} --fast
              </code>
            </div>

            <div className="run-option">
              <div className="run-option-label">Full suite (all benchmarks):</div>
              <code
                className="curl-code"
                onClick={() => copyToClipboard(
                  `curl -sL https://raw.githubusercontent.com/mkoskinen/benchcom/main/benchcom.sh | bash -s -- --api-url ${DISPLAY_URL} --full`
                )}
                title="Click to copy"
              >
                ... | bash -s -- --api-url {DISPLAY_URL} --full
              </code>
            </div>

            <div className="run-option">
              <div className="run-option-label">Skip dependency install (no sudo):</div>
              <code
                className="curl-code"
                onClick={() => copyToClipboard(
                  `curl -sL https://raw.githubusercontent.com/mkoskinen/benchcom/main/benchcom.sh | bash -s -- --api-url ${DISPLAY_URL} --no-install-deps`
                )}
                title="Click to copy"
              >
                ... | bash -s -- --api-url {DISPLAY_URL} --no-install-deps
              </code>
            </div>

            <div className="run-option">
              <div className="run-option-label">With authentication:</div>
              <code
                className="curl-code"
                onClick={() => copyToClipboard(
                  `curl -sL https://raw.githubusercontent.com/mkoskinen/benchcom/main/benchcom.sh | bash -s -- --api-url ${DISPLAY_URL} --api-username USER --api-password PASS`
                )}
                title="Click to copy"
              >
                ... | bash -s -- --api-url {DISPLAY_URL} --api-username USER --api-password PASS
              </code>
            </div>

            <div className="run-option">
              <div className="run-option-label">Download and run manually:</div>
              <code
                className="curl-code"
                onClick={() => copyToClipboard(
                  `curl -sLO https://raw.githubusercontent.com/mkoskinen/benchcom/main/benchcom.sh && chmod +x benchcom.sh && ./benchcom.sh --api-url ${DISPLAY_URL}`
                )}
                title="Click to copy"
              >
                curl -sLO .../benchcom.sh && chmod +x benchcom.sh && ./benchcom.sh --api-url {DISPLAY_URL}
              </code>
            </div>
          </div>
        )}
      </div>

      {view === "list" && (
        <>
          {/* Test type navigation */}
          <TestNav onSelectTest={handleSelectStats} />

          {selectedForCompare.length > 0 && (
            <div className="compare-bar">
              <span>{selectedForCompare.length} selected for comparison</span>
              <button
                onClick={handleCompare}
                disabled={selectedForCompare.length < 2}
              >
                Compare
              </button>
              <button onClick={clearSelection}>Clear</button>
            </div>
          )}

          {error && <div className="error">{error}</div>}

          {/* Leaderboard with tabs */}
          <div className="leaderboard">
            <div className="leaderboard-header">
              <h3 className="section-title">Top 10</h3>
              <div className="leaderboard-tabs">
                {leaderboardTabs.map((tab, idx) => (
                  <span
                    key={idx}
                    className={`leaderboard-tab ${leaderboardTab === idx ? "active" : ""}`}
                    onClick={() => handleLeaderboardTabChange(idx)}
                  >
                    {tab.label}
                  </span>
                ))}
              </div>
              <span
                className="section-link"
                onClick={() => handleSelectStats(leaderboardTabs[leaderboardTab].test)}
              >
                [view all]
              </span>
            </div>
            {leaderboard.length > 0 ? (
              <div className="leaderboard-list">
                {leaderboard.map((stat, idx) => (
                  <div key={idx} className="leaderboard-item">
                    <span className="leaderboard-rank">#{idx + 1}</span>
                    <span className="leaderboard-name">
                      {leaderboardTabs[leaderboardTab].groupBy === "cpu"
                        ? (stat.cpu_model || "Unknown")
                        : (stat.system_type || stat.cpu_model || "Unknown")}
                    </span>
                    <span className="leaderboard-value">
                      {formatLeaderboardValue(stat.median_value, stat.unit)} {stat.unit}
                    </span>
                    <span className="leaderboard-meta">n={stat.sample_count}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="leaderboard-empty">No data available</div>
            )}
          </div>

          <h3 className="section-title">Recent Submissions</h3>

          {loading ? (
            <div className="loading">Loading...</div>
          ) : (
            <BenchmarkList
              benchmarks={benchmarks}
              onSelect={handleSelect}
              selectedForCompare={selectedForCompare}
              onToggleCompare={handleToggleCompare}
            />
          )}
        </>
      )}

      {view === "detail" && selectedBenchmark && (
        <BenchmarkDetail benchmarkId={selectedBenchmark} onBack={handleBack} />
      )}

      {view === "compare" && (
        <BenchmarkCompare
          benchmarkIds={selectedForCompare}
          onBack={handleBack}
        />
      )}

      {view === "test-results" && selectedTest && (
        <TestResultsView
          testName={selectedTest}
          onBack={handleBack}
          onCompare={handleCompareFromTest}
          onSelectTest={handleSelectTest}
        />
      )}

      {view === "stats" && selectedTest && (
        <StatsView
          testName={selectedTest}
          onBack={handleBack}
          onViewFull={handleSelectTest}
          onSelectTest={handleSelectStats}
        />
      )}
    </div>
  );
}

export default App;
