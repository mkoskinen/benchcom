import { useState, useEffect } from "react";
import BenchmarkList from "./components/BenchmarkList";
import BenchmarkDetail from "./components/BenchmarkDetail";
import BenchmarkCompare from "./components/BenchmarkCompare";
import TestResultsView from "./components/TestResultsView";
import { Benchmark, TestInfo } from "./types";
import axios from "axios";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const LOGO = `██████╗ ███████╗███╗   ██╗ ██████╗██╗  ██╗ ██████╗ ██████╗ ███╗   ███╗
██╔══██╗██╔════╝████╗  ██║██╔════╝██║  ██║██╔════╝██╔═══██╗████╗ ████║
██████╔╝█████╗  ██╔██╗ ██║██║     ███████║██║     ██║   ██║██╔████╔██║
██╔══██╗██╔══╝  ██║╚██╗██║██║     ██╔══██║██║     ██║   ██║██║╚██╔╝██║
██████╔╝███████╗██║ ╚████║╚██████╗██║  ██║╚██████╗╚██████╔╝██║ ╚═╝ ██║
╚═════╝ ╚══════╝╚═╝  ╚═══╝ ╚═════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═╝     ╚═╝`;

type View = "list" | "detail" | "compare" | "test-results";

function App() {
  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
  const [tests, setTests] = useState<TestInfo[]>([]);
  const [view, setView] = useState<View>("list");
  const [selectedBenchmark, setSelectedBenchmark] = useState<number | null>(
    null
  );
  const [selectedTest, setSelectedTest] = useState<string | null>(null);
  const [selectedForCompare, setSelectedForCompare] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [architecture, setArchitecture] = useState("");
  const [hostname, setHostname] = useState("");

  useEffect(() => {
    fetchBenchmarks();
    fetchTests();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [architecture, hostname]);

  const fetchBenchmarks = async () => {
    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams();
      params.append("limit", "20");
      if (architecture) params.append("architecture", architecture);
      if (hostname) params.append("hostname", hostname);

      const response = await axios.get(
        `${API_URL}/api/v1/benchmarks?${params.toString()}`
      );

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

  const handleSelect = (id: number) => {
    setSelectedBenchmark(id);
    setView("detail");
  };

  const handleSelectTest = (testName: string) => {
    setSelectedTest(testName);
    setView("test-results");
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

  // Group tests by category
  const testsByCategory = tests.reduce(
    (acc, test) => {
      const cat = test.test_category || "other";
      if (!acc[cat]) acc[cat] = [];
      acc[cat].push(test);
      return acc;
    },
    {} as Record<string, TestInfo[]>
  );

  return (
    <div className="app">
      <header className="header">
        <pre className="logo">{LOGO}</pre>
      </header>

      {view === "list" && (
        <>
          {/* Test type navigation */}
          {tests.length > 0 && (
            <div className="test-nav">
              <span className="test-nav-label">Results by test:</span>
              {Object.entries(testsByCategory).map(([category, catTests]) => (
                <span key={category} className="test-nav-group">
                  <span className="test-nav-category">{category}:</span>
                  {catTests.map((test) => (
                    <span
                      key={test.test_name}
                      className="test-nav-link"
                      onClick={() => handleSelectTest(test.test_name)}
                    >
                      {test.test_name} ({test.result_count})
                    </span>
                  ))}
                </span>
              ))}
            </div>
          )}

          <div className="filters">
            <label>Host:</label>
            <input
              type="text"
              placeholder="hostname"
              value={hostname}
              onChange={(e) => setHostname(e.target.value)}
            />
            <label>Arch:</label>
            <input
              type="text"
              placeholder="x86_64"
              value={architecture}
              onChange={(e) => setArchitecture(e.target.value)}
            />
            <button onClick={fetchBenchmarks}>Refresh</button>
          </div>

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

          <h3 className="section-title">Recent Submissions (up to 20)</h3>

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
    </div>
  );
}

export default App;
