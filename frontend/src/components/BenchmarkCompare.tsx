import { useState, useEffect } from "react";
import axios from "axios";
import { BenchmarkDetail } from "../types";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface BenchmarkCompareProps {
  benchmarkIds: number[];
  onBack: () => void;
}

function BenchmarkCompare({ benchmarkIds, onBack }: BenchmarkCompareProps) {
  const [benchmarks, setBenchmarks] = useState<BenchmarkDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchBenchmarks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [benchmarkIds]);

  const fetchBenchmarks = async () => {
    try {
      setLoading(true);
      setError(null);

      const responses = await Promise.all(
        benchmarkIds.map((id) =>
          axios.get(`${API_URL}/api/v1/benchmarks/${id}`),
        ),
      );

      setBenchmarks(responses.map((r) => r.data));
    } catch (err) {
      setError("Failed to fetch benchmarks");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const formatValue = (value: number | null) => {
    if (value === null) return "—";
    return value.toLocaleString(undefined, { maximumFractionDigits: 3 });
  };

  // Get all unique test names across all benchmarks
  const getAllTests = () => {
    const testMap = new Map<
      string,
      { category: string; unit: string | null }
    >();

    benchmarks.forEach((b) => {
      b.results.forEach((r) => {
        if (!testMap.has(r.test_name)) {
          testMap.set(r.test_name, { category: r.test_category, unit: r.unit });
        }
      });
    });

    // Group by category
    const byCategory: Record<string, { name: string; unit: string | null }[]> =
      {};
    testMap.forEach((info, name) => {
      if (!byCategory[info.category]) {
        byCategory[info.category] = [];
      }
      byCategory[info.category].push({ name, unit: info.unit });
    });

    return byCategory;
  };

  // Get result value for a specific benchmark and test
  const getResult = (benchmark: BenchmarkDetail, testName: string) => {
    const result = benchmark.results.find((r) => r.test_name === testName);
    return result?.value ?? null;
  };

  // Find best (min for time, max for throughput)
  const findBest = (testName: string, unit: string | null) => {
    const values = benchmarks
      .map((b) => ({ id: b.id, value: getResult(b, testName) }))
      .filter((v) => v.value !== null);

    if (values.length === 0) return null;

    // Lower is better for seconds/nanoseconds (latency), higher is better for everything else
    const u = unit?.toLowerCase() ?? "";
    const isLowerBetter = u.includes("second") || u === "ns";

    return values.reduce((best, curr) => {
      if (best.value === null) return curr;
      if (curr.value === null) return best;
      if (isLowerBetter) {
        return curr.value < best.value ? curr : best;
      }
      return curr.value > best.value ? curr : best;
    }).id;
  };

  // Calculate percentage difference from best
  const getPercentage = (
    value: number | null,
    testName: string,
    unit: string | null,
    benchmarkId: number
  ) => {
    if (value === null) return null;
    const bestId = findBest(testName, unit);
    if (bestId === null || bestId === benchmarkId) return null;

    const bestBenchmark = benchmarks.find((b) => b.id === bestId);
    if (!bestBenchmark) return null;

    const bestValue = getResult(bestBenchmark, testName);
    if (bestValue === null || bestValue === 0) return null;

    const isLowerBetter = unit?.toLowerCase().includes("second");

    if (isLowerBetter) {
      // For time: how much slower (higher is worse)
      const pct = ((value - bestValue) / bestValue) * 100;
      return `+${pct.toFixed(1)}%`;
    } else {
      // For throughput: how much slower (lower is worse)
      const pct = ((bestValue - value) / bestValue) * 100;
      return `-${pct.toFixed(1)}%`;
    }
  };

  if (loading) {
    return <div className="loading">Loading...</div>;
  }

  if (error) {
    return (
      <div>
        <span className="back-link" onClick={onBack}>
          ← Back
        </span>
        <div className="error">{error}</div>
      </div>
    );
  }

  const testsByCategory = getAllTests();

  return (
    <div>
      <span className="back-link" onClick={onBack}>
        ← Back to list
      </span>

      <h2 className="compare-title">
        Comparison ({benchmarks.length} systems)
      </h2>

      {/* System info comparison */}
      <table className="compare-table">
        <thead>
          <tr>
            <th></th>
            {benchmarks.map((b) => (
              <th key={b.id}>{b.hostname}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            <th>Architecture</th>
            {benchmarks.map((b) => (
              <td key={b.id}>{b.architecture}</td>
            ))}
          </tr>
          <tr>
            <th>CPU</th>
            {benchmarks.map((b) => (
              <td key={b.id}>{b.cpu_model || "—"}</td>
            ))}
          </tr>
          <tr>
            <th>Cores</th>
            {benchmarks.map((b) => (
              <td key={b.id}>{b.cpu_cores || "—"}</td>
            ))}
          </tr>
          <tr>
            <th>Memory</th>
            {benchmarks.map((b) => (
              <td key={b.id}>
                {b.total_memory_mb
                  ? Math.round(b.total_memory_mb / 1024) + " GB"
                  : "—"}
              </td>
            ))}
          </tr>
          <tr>
            <th>Kernel</th>
            {benchmarks.map((b) => (
              <td key={b.id}>{b.kernel_version || "—"}</td>
            ))}
          </tr>
        </tbody>
      </table>

      {/* Results comparison by category */}
      {Object.entries(testsByCategory).map(([category, tests]) => (
        <div key={category} className="results-category">
          <h3>{category.toUpperCase()}</h3>
          <table className="compare-table">
            <thead>
              <tr>
                <th>Test</th>
                {benchmarks.map((b) => (
                  <th key={b.id}>{b.hostname}</th>
                ))}
                <th>Unit</th>
              </tr>
            </thead>
            <tbody>
              {tests.map((test) => {
                const bestId = findBest(test.name, test.unit);
                return (
                  <tr key={test.name}>
                    <td>{test.name}</td>
                    {benchmarks.map((b) => {
                      const value = getResult(b, test.name);
                      const isBest = b.id === bestId;
                      const pct = getPercentage(
                        value,
                        test.name,
                        test.unit,
                        b.id
                      );
                      return (
                        <td
                          key={b.id}
                          className={`value-col ${isBest ? "best" : ""}`}
                        >
                          {formatValue(value)}
                          {pct && <span className="pct-diff"> ({pct})</span>}
                        </td>
                      );
                    })}
                    <td className="unit-col">{test.unit || ""}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}

export default BenchmarkCompare;
