import { useState, useEffect, useMemo } from "react";
import axios from "axios";
import { TestResult } from "../types";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

type SortField = "cpu_model" | "hostname" | "architecture" | "value" | "submitted_at";
type SortDirection = "asc" | "desc";

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
  const [sortField, setSortField] = useState<SortField>("value");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

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

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      // Default to desc for value (higher is usually better), asc for strings
      setSortDirection(field === "value" ? "desc" : "asc");
    }
  };

  const getSortIndicator = (field: SortField) => {
    if (sortField !== field) return "";
    return sortDirection === "asc" ? " ▲" : " ▼";
  };

  const unit = results.length > 0 ? results[0].unit : null;
  const isLowerBetter = unit?.toLowerCase().includes("second");

  const sortedResults = useMemo(() => {
    return [...results].sort((a, b) => {
      let aVal = a[sortField];
      let bVal = b[sortField];

      // Handle nulls
      if (aVal === null) return 1;
      if (bVal === null) return -1;

      // String comparison
      if (typeof aVal === "string" && typeof bVal === "string") {
        const cmp = aVal.localeCompare(bVal);
        return sortDirection === "asc" ? cmp : -cmp;
      }

      // Number comparison
      if (typeof aVal === "number" && typeof bVal === "number") {
        return sortDirection === "asc" ? aVal - bVal : bVal - aVal;
      }

      return 0;
    });
  }, [results, sortField, sortDirection]);

  // Find best value for percentage calculation
  const bestValue = useMemo(() => {
    if (results.length === 0) return null;
    const values = results.map(r => r.value).filter((v): v is number => v !== null);
    if (values.length === 0) return null;
    return isLowerBetter ? Math.min(...values) : Math.max(...values);
  }, [results, isLowerBetter]);

  const getPercentage = (value: number | null) => {
    if (value === null || bestValue === null || bestValue === 0) return null;
    if (value === bestValue) return null; // Best result, no percentage

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
            <th className="sortable" onClick={() => handleSort("cpu_model")}>
              CPU{getSortIndicator("cpu_model")}
            </th>
            <th className="sortable" onClick={() => handleSort("hostname")}>
              Host{getSortIndicator("hostname")}
            </th>
            <th className="sortable" onClick={() => handleSort("architecture")}>
              Arch{getSortIndicator("architecture")}
            </th>
            <th className="value-col sortable" onClick={() => handleSort("value")}>
              Result{getSortIndicator("value")}
            </th>
            <th className="pct-col">vs Best</th>
            <th>Unit</th>
          </tr>
        </thead>
        <tbody>
          {sortedResults.map((result) => {
            const isSelected = selectedForCompare.includes(result.run_id);
            const pct = getPercentage(result.value);
            const isBest = result.value === bestValue;
            return (
              <tr
                key={result.id}
                className={`${isBest ? "best-row" : ""} ${isSelected ? "selected" : ""}`}
              >
                <td className="checkbox-col">
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => handleToggleCompare(result.run_id)}
                  />
                </td>
                <td>{result.cpu_model || "—"}</td>
                <td>{result.hostname}</td>
                <td>{result.architecture}</td>
                <td className={`value-col ${isBest ? "best" : ""}`}>
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
