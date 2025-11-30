import { useState, useEffect } from "react";
import axios from "axios";
import { TestResult } from "../types";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface TestResultsViewProps {
  testName: string;
  onBack: () => void;
  onCompare: (runIds: number[]) => void;
}

function TestResultsView({ testName, onBack, onCompare }: TestResultsViewProps) {
  const [results, setResults] = useState<TestResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedForCompare, setSelectedForCompare] = useState<number[]>([]);

  useEffect(() => {
    fetchResults();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [testName]);

  const fetchResults = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await axios.get(
        `${API_URL}/api/v1/results/by-test?test_name=${encodeURIComponent(testName)}`
      );
      setResults(response.data);
    } catch (err) {
      setError("Failed to fetch results");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const formatValue = (value: number | null) => {
    if (value === null) return "—";
    return value.toLocaleString(undefined, { maximumFractionDigits: 3 });
  };

  const handleToggleCompare = (runId: number) => {
    setSelectedForCompare((prev) =>
      prev.includes(runId)
        ? prev.filter((x) => x !== runId)
        : prev.length < 4
          ? [...prev, runId]
          : prev
    );
  };

  const handleCompare = () => {
    if (selectedForCompare.length >= 2) {
      onCompare(selectedForCompare);
    }
  };

  const getPercentage = (value: number | null, index: number) => {
    if (value === null || results.length === 0) return null;
    const bestValue = results[0].value;
    if (bestValue === null || bestValue === 0) return null;
    if (index === 0) return null; // Best result, no percentage

    const unit = results[0].unit?.toLowerCase() || "";
    const isLowerBetter = unit.includes("second");

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

  const unit = results.length > 0 ? results[0].unit : null;
  const isLowerBetter = unit?.toLowerCase().includes("second");

  return (
    <div>
      <span className="back-link" onClick={onBack}>
        ← Back to list
      </span>

      <h2 className="test-title">
        {testName}
        <span className="test-subtitle">
          {" "}
          — {isLowerBetter ? "lower is better" : "higher is better"}
        </span>
      </h2>

      {selectedForCompare.length > 0 && (
        <div className="compare-bar">
          <span>{selectedForCompare.length} selected for comparison</span>
          <button
            onClick={handleCompare}
            disabled={selectedForCompare.length < 2}
          >
            Compare Systems
          </button>
          <button onClick={() => setSelectedForCompare([])}>Clear</button>
        </div>
      )}

      <table className="results-table">
        <thead>
          <tr>
            <th className="checkbox-col">Compare</th>
            <th className="rank-col">#</th>
            <th>CPU</th>
            <th>Host</th>
            <th>Arch</th>
            <th className="value-col">Result</th>
            <th className="pct-col">vs Best</th>
            <th>Unit</th>
          </tr>
        </thead>
        <tbody>
          {results.map((result, index) => {
            const isSelected = selectedForCompare.includes(result.run_id);
            const pct = getPercentage(result.value, index);
            return (
              <tr
                key={result.id}
                className={`${index === 0 ? "best-row" : ""} ${isSelected ? "selected" : ""}`}
              >
                <td className="checkbox-col">
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => handleToggleCompare(result.run_id)}
                  />
                </td>
                <td className="rank-col">{index + 1}</td>
                <td>{result.cpu_model || "—"}</td>
                <td>{result.hostname}</td>
                <td>{result.architecture}</td>
                <td className={`value-col ${index === 0 ? "best" : ""}`}>
                  {formatValue(result.value)}
                </td>
                <td className={`pct-col ${pct ? "slower" : ""}`}>{pct || "—"}</td>
                <td className="unit-col">{unit || ""}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default TestResultsView;
