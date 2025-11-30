import { useState, useEffect } from "react";
import axios from "axios";
import { BenchmarkDetail as BenchmarkDetailType } from "../types";
import { useAuth } from "../context/AuthContext";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface BenchmarkDetailProps {
  benchmarkId: number;
  onBack: () => void;
}

function BenchmarkDetail({ benchmarkId, onBack }: BenchmarkDetailProps) {
  const { token } = useAuth();
  const [benchmark, setBenchmark] = useState<BenchmarkDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showConsoleOutput, setShowConsoleOutput] = useState(false);

  useEffect(() => {
    fetchBenchmark();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [benchmarkId, token]);

  const fetchBenchmark = async () => {
    try {
      setLoading(true);
      setError(null);
      const headers: Record<string, string> = {};
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
      const response = await axios.get(
        `${API_URL}/api/v1/benchmarks/${benchmarkId}`,
        { headers }
      );
      setBenchmark(response.data);
    } catch (err) {
      setError("Failed to fetch benchmark details");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "—";
    const d = new Date(dateString);
    return d.toLocaleDateString() + " " + d.toLocaleTimeString();
  };

  const formatValue = (value: number | null) => {
    if (value === null) return "—";
    return value.toLocaleString(undefined, { maximumFractionDigits: 3 });
  };

  const cropHostname = (hostname: string) => {
    const dotIndex = hostname.indexOf(".");
    return dotIndex > 0 ? hostname.substring(0, dotIndex) : hostname;
  };

  const formatDmiInfo = (dmi: Record<string, string> | null) => {
    if (!dmi) return null;
    // Show manufacturer + product (most useful DMI fields)
    const parts = [];
    if (dmi.manufacturer && dmi.manufacturer !== "Unknown") {
      parts.push(dmi.manufacturer);
    }
    if (dmi.product && dmi.product !== "Unknown") {
      parts.push(dmi.product);
    }
    // For Apple Silicon, also show chip
    if (dmi.chip) {
      parts.push(dmi.chip);
    }
    return parts.length > 0 ? parts.join(" ") : null;
  };

  const groupResultsByCategory = (results: BenchmarkDetailType["results"]) => {
    const grouped: Record<string, BenchmarkDetailType["results"]> = {};
    results.forEach((result) => {
      const category = result.test_category || "other";
      if (!grouped[category]) {
        grouped[category] = [];
      }
      grouped[category].push(result);
    });
    return grouped;
  };

  if (loading) {
    return <div className="loading">Loading...</div>;
  }

  if (error || !benchmark) {
    return (
      <div>
        <span className="back-link" onClick={onBack}>
          ← Back
        </span>
        <div className="error">{error || "Benchmark not found"}</div>
      </div>
    );
  }

  const groupedResults = groupResultsByCategory(benchmark.results);

  return (
    <div>
      <span className="back-link" onClick={onBack}>
        ← Back to list
      </span>

      {/* System info header */}
      <table className="info-table">
        <tbody>
          <tr>
            <th>Host</th>
            <td>
              <strong>{cropHostname(benchmark.hostname)}</strong>
            </td>
            <th>Arch</th>
            <td>{benchmark.architecture}</td>
            <th>Submitted</th>
            <td>{formatDate(benchmark.submitted_at)}</td>
          </tr>
          <tr>
            <th>CPU</th>
            <td colSpan={3}>{benchmark.cpu_model || "—"}</td>
            <th>Cores</th>
            <td>{benchmark.cpu_cores || "—"}</td>
          </tr>
          <tr>
            <th>Memory</th>
            <td>
              {benchmark.total_memory_mb
                ? Math.round(benchmark.total_memory_mb / 1024) + " GB"
                : "—"}
            </td>
            <th>Kernel</th>
            <td colSpan={3}>{benchmark.kernel_version || "—"}</td>
          </tr>
          {formatDmiInfo(benchmark.dmi_info) && (
            <tr>
              <th>System</th>
              <td colSpan={5}>{formatDmiInfo(benchmark.dmi_info)}</td>
            </tr>
          )}
        </tbody>
      </table>

      {/* Results by category */}
      {Object.entries(groupedResults).map(([category, results]) => (
        <div key={category} className="results-category">
          <h3>{category.toUpperCase()}</h3>
          <table className="results-table">
            <thead>
              <tr>
                <th>Test</th>
                <th className="value-col">Result</th>
                <th>Unit</th>
              </tr>
            </thead>
            <tbody>
              {results.map((result) => (
                <tr key={result.id}>
                  <td>{result.test_name}</td>
                  <td className="value-col">{formatValue(result.value)}</td>
                  <td className="unit-col">{result.unit || ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}

      {/* Sensitive data section - only visible to admins/owners */}
      {(benchmark.submitter_ip || benchmark.console_output) && (
        <div className="admin-section">
          <h3>Submission Details</h3>
          <table className="info-table">
            <tbody>
              {benchmark.submitter_ip && (
                <tr>
                  <th>Submitter IP</th>
                  <td>{benchmark.submitter_ip}</td>
                </tr>
              )}
              {benchmark.user_id && (
                <tr>
                  <th>User ID</th>
                  <td>{benchmark.user_id}</td>
                </tr>
              )}
              {benchmark.username && (
                <tr>
                  <th>Username</th>
                  <td>{benchmark.username}</td>
                </tr>
              )}
            </tbody>
          </table>

          {benchmark.console_output && (
            <div className="console-output-section">
              <span
                className="console-toggle"
                onClick={() => setShowConsoleOutput(!showConsoleOutput)}
              >
                {showConsoleOutput ? "[-] Hide" : "[+] Show"} Console Output
              </span>
              {showConsoleOutput && (
                <pre className="console-output">{benchmark.console_output}</pre>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default BenchmarkDetail;
