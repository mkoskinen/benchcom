import { useState, useEffect } from "react";
import BenchmarkList from "./components/BenchmarkList";
import BenchmarkDetail from "./components/BenchmarkDetail";
import BenchmarkCompare from "./components/BenchmarkCompare";
import TestResultsView from "./components/TestResultsView";
import StatsView from "./components/StatsView";
import AuthModal from "./components/AuthModal";
import { useAuth } from "./context/AuthContext";
import { Benchmark, TestInfo, BenchmarkStat } from "./types";
import axios from "axios";

// Derive API URL from current location (frontend:3000 -> api:8000)
const API_URL = import.meta.env.VITE_API_URL || "";

const LOGO = `██████╗ ███████╗███╗   ██╗ ██████╗██╗  ██╗ ██████╗ ██████╗ ███╗   ███╗
██╔══██╗██╔════╝████╗  ██║██╔════╝██║  ██║██╔════╝██╔═══██╗████╗ ████║
██████╔╝█████╗  ██╔██╗ ██║██║     ███████║██║     ██║   ██║██╔████╔██║
██╔══██╗██╔══╝  ██║╚██╗██║██║     ██╔══██║██║     ██║   ██║██║╚██╔╝██║
██████╔╝███████╗██║ ╚████║╚██████╗██║  ██║╚██████╗╚██████╔╝██║ ╚═╝ ██║
╚═════╝ ╚══════╝╚═╝  ╚═══╝ ╚═════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═╝     ╚═╝`;

type View = "list" | "detail" | "compare" | "test-results" | "stats";

function App() {
  const { user, logout, isLoading: authLoading } = useAuth();
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [showRunOptions, setShowRunOptions] = useState(false);
  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
  const [tests, setTests] = useState<TestInfo[]>([]);
  const [leaderboard, setLeaderboard] = useState<BenchmarkStat[]>([]);
  const [leaderboardTab, setLeaderboardTab] = useState(0);
  const [view, setView] = useState<View>("list");

  // Leaderboard tab configurations
  const leaderboardTabs = [
    { label: "CPU MT (system)", test: "passmark_cpu_mt", groupBy: "system" },
    { label: "CPU MT (CPU)", test: "passmark_cpu_mt", groupBy: "cpu" },
    { label: "CPU ST (system)", test: "passmark_cpu_single", groupBy: "system" },
    { label: "Memory (system)", test: "passmark_memory", groupBy: "system" },
    { label: "AES256 (CPU)", test: "openssl_aes256", groupBy: "cpu" },
    { label: "SHA256 (CPU)", test: "openssl_sha256", groupBy: "cpu" },
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

  useEffect(() => {
    fetchBenchmarks();
    fetchTests();
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

  const fetchTests = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/v1/tests`);
      setTests(response.data);
    } catch (err) {
      console.error("Failed to fetch tests:", err);
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
  };

  const handleSelectTest = (testName: string) => {
    setSelectedTest(testName);
    setView("test-results");
  };

  const handleSelectStats = (testName: string) => {
    setSelectedTest(testName);
    setView("stats");
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
    }
  };

  const handleCompareFromTest = (runIds: number[]) => {
    setSelectedForCompare(runIds);
    setView("compare");
  };

  const handleBack = () => {
    setView("list");
    setSelectedBenchmark(null);
    setSelectedTest(null);
  };

  const clearSelection = () => {
    setSelectedForCompare([]);
  };

  // Group tests by category and sort
  const testsByCategory = tests.reduce(
    (acc, test) => {
      const cat = test.test_category || "other";
      if (!acc[cat]) acc[cat] = [];
      acc[cat].push(test);
      return acc;
    },
    {} as Record<string, TestInfo[]>
  );

  // Sort tests within each category by name
  Object.values(testsByCategory).forEach(catTests => {
    catTests.sort((a, b) => a.test_name.localeCompare(b.test_name));
  });

  // Define category order (most important first)
  const categoryOrder = ["cpu", "memory", "disk", "compression", "cryptography", "other"];
  const sortedCategories = Object.keys(testsByCategory).sort((a, b) => {
    const aIdx = categoryOrder.indexOf(a);
    const bIdx = categoryOrder.indexOf(b);
    if (aIdx === -1 && bIdx === -1) return a.localeCompare(b);
    if (aIdx === -1) return 1;
    if (bIdx === -1) return -1;
    return aIdx - bIdx;
  });

  const goHome = () => {
    setView("list");
    setSelectedBenchmark(null);
    setSelectedTest(null);
  };

  return (
    <div className="app">
      <header className="header">
        <pre className="logo clickable" onClick={goHome}>{LOGO}</pre>
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
              `curl -sL https://raw.githubusercontent.com/mkoskinen/benchcom/main/benchcom.sh | bash -s -- --api-url ${API_URL}`
            )}
            title="Click to copy"
          >
            curl -sL https://raw.githubusercontent.com/mkoskinen/benchcom/main/benchcom.sh | bash -s -- --api-url {API_URL}
          </code>
          <span
            className="expand-toggle"
            onClick={() => setShowRunOptions(!showRunOptions)}
          >
            {showRunOptions ? "[-] less" : "[+] more options"}
          </span>
        </div>

        {showRunOptions && (
          <div className="run-options">
            <div className="run-option">
              <div className="run-option-label">Quick mode (OpenSSL only):</div>
              <code
                className="curl-code"
                onClick={() => copyToClipboard(
                  `curl -sL https://raw.githubusercontent.com/mkoskinen/benchcom/main/benchcom.sh | bash -s -- --api-url ${API_URL} --fast`
                )}
                title="Click to copy"
              >
                ... | bash -s -- --api-url {API_URL} --fast
              </code>
            </div>

            <div className="run-option">
              <div className="run-option-label">Full suite (all benchmarks):</div>
              <code
                className="curl-code"
                onClick={() => copyToClipboard(
                  `curl -sL https://raw.githubusercontent.com/mkoskinen/benchcom/main/benchcom.sh | bash -s -- --api-url ${API_URL} --full`
                )}
                title="Click to copy"
              >
                ... | bash -s -- --api-url {API_URL} --full
              </code>
            </div>

            <div className="run-option">
              <div className="run-option-label">Skip dependency install (no sudo):</div>
              <code
                className="curl-code"
                onClick={() => copyToClipboard(
                  `curl -sL https://raw.githubusercontent.com/mkoskinen/benchcom/main/benchcom.sh | bash -s -- --api-url ${API_URL} --no-install-deps`
                )}
                title="Click to copy"
              >
                ... | bash -s -- --api-url {API_URL} --no-install-deps
              </code>
            </div>

            <div className="run-option">
              <div className="run-option-label">With authentication:</div>
              <code
                className="curl-code"
                onClick={() => copyToClipboard(
                  `curl -sL https://raw.githubusercontent.com/mkoskinen/benchcom/main/benchcom.sh | bash -s -- --api-url ${API_URL} --api-username YOUR_USER --api-password YOUR_PASS`
                )}
                title="Click to copy"
              >
                ... | bash -s -- --api-url {API_URL} --api-username USER --api-password PASS
              </code>
            </div>

            <div className="run-option">
              <div className="run-option-label">Download and run manually:</div>
              <code
                className="curl-code"
                onClick={() => copyToClipboard(
                  `curl -sLO https://raw.githubusercontent.com/mkoskinen/benchcom/main/benchcom.sh && chmod +x benchcom.sh && ./benchcom.sh --api-url ${API_URL}`
                )}
                title="Click to copy"
              >
                curl -sLO .../benchcom.sh && chmod +x benchcom.sh && ./benchcom.sh --api-url {API_URL}
              </code>
            </div>
          </div>
        )}
      </div>

      {view === "list" && (
        <>
          {/* Test type navigation */}
          {tests.length > 0 && (
            <div className="test-nav">
              <span className="test-nav-label">Results by test:</span>
              {sortedCategories.map((category) => (
                <span key={category} className="test-nav-group">
                  <span className="test-nav-category">{category}:</span>
                  {testsByCategory[category].map((test) => (
                    <span key={test.test_name} className="test-nav-item">
                      <span
                        className="test-nav-link"
                        onClick={() => handleSelectStats(test.test_name)}
                        title="View median stats by CPU/System"
                      >
                        {test.test_name}
                      </span>
                    </span>
                  ))}
                </span>
              ))}
            </div>
          )}

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
                    onClick={() => setLeaderboardTab(idx)}
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
                      {stat.median_value?.toLocaleString(undefined, { maximumFractionDigits: 0 })} {stat.unit}
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
        />
      )}

      {view === "stats" && selectedTest && (
        <StatsView
          testName={selectedTest}
          onBack={handleBack}
          onViewFull={handleSelectTest}
        />
      )}
    </div>
  );
}

export default App;
