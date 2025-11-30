import { useState, useEffect, useMemo } from "react";
import axios from "axios";
import { BenchmarkStat } from "../types";
import { getTestDescription } from "../testDescriptions";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

type GroupBy = "cpu" | "system" | "architecture";
type ViewMode = "table" | "chart";

interface StatsViewProps {
  testName: string;
  onBack: () => void;
  onViewFull?: (testName: string) => void;
}

function StatsView({ testName, onBack, onViewFull }: StatsViewProps) {
  const [stats, setStats] = useState<BenchmarkStat[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [groupBy, setGroupBy] = useState<GroupBy>("cpu");
  const [viewMode, setViewMode] = useState<ViewMode>("chart");

  useEffect(() => {
    fetchStats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [testName, groupBy]);

  const fetchStats = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await axios.get(
        `${API_URL}/api/v1/stats/by-test?test_name=${encodeURIComponent(testName)}&group_by=${groupBy}&limit=30`
      );
      setStats(response.data);
    } catch (err) {
      setError("Failed to fetch stats. Try refreshing stats data.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const formatValue = (value: number | null) => {
    if (value === null) return "—";
    return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  };

  const unit = stats.length > 0 ? stats[0].unit : null;
  const description = getTestDescription(testName);
  const isLowerBetter = useMemo(() => {
    return unit?.toLowerCase()?.includes("second") ?? false;
  }, [unit]);

  const bestValue = useMemo(() => {
    if (stats.length === 0) return null;
    const values = stats.map(s => s.median_value).filter((v): v is number => v !== null);
    if (values.length === 0) return null;
    return isLowerBetter ? Math.min(...values) : Math.max(...values);
  }, [stats, isLowerBetter]);

  const maxValue = useMemo(() => {
    if (stats.length === 0) return 0;
    const values = stats.map(s => s.median_value).filter((v): v is number => v !== null);
    return Math.max(...values);
  }, [stats]);

  const getLabel = (stat: BenchmarkStat) => {
    if (groupBy === "cpu") return stat.cpu_model || "Unknown";
    if (groupBy === "system") return stat.system_type || "Unknown";
    return stat.architecture;
  };

  const getPercentage = (value: number | null) => {
    if (value === null || bestValue === null || bestValue === 0) return null;
    if (value === bestValue) return null;

    if (isLowerBetter) {
      const pct = ((value - bestValue) / bestValue) * 100;
      return `+${pct.toFixed(1)}%`;
    } else {
      const pct = ((bestValue - value) / bestValue) * 100;
      return `-${pct.toFixed(1)}%`;
    }
  };

  const getBarWidth = (value: number | null) => {
    if (value === null || maxValue === 0) return 0;
    if (isLowerBetter) {
      const minValue = stats[0]?.median_value ?? 0;
      if (minValue === 0) return 100;
      return (minValue / value) * 100;
    }
    return (value / maxValue) * 100;
  };

  if (loading) {
    return <div className="loading">Loading stats...</div>;
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
          {" "}— Median by {groupBy} ({isLowerBetter ? "lower is better" : "higher is better"})
        </span>
      </h2>

      {description && (
        <p className="test-description">{description}</p>
      )}

      <div className="stats-controls">
        <div className="group-by-toggle">
          <span className="toggle-label">Group by:</span>
          <button
            className={groupBy === "cpu" ? "active" : ""}
            onClick={() => setGroupBy("cpu")}
          >
            CPU
          </button>
          <button
            className={groupBy === "system" ? "active" : ""}
            onClick={() => setGroupBy("system")}
          >
            System
          </button>
          <button
            className={groupBy === "architecture" ? "active" : ""}
            onClick={() => setGroupBy("architecture")}
          >
            Arch
          </button>
        </div>

        <div className="view-toggle">
          <button
            className={viewMode === "chart" ? "active" : ""}
            onClick={() => setViewMode("chart")}
          >
            Chart
          </button>
          <button
            className={viewMode === "table" ? "active" : ""}
            onClick={() => setViewMode("table")}
          >
            Table
          </button>
        </div>
      </div>

      {stats.length === 0 ? (
        <div className="empty">
          No stats available. Stats are generated after benchmark submissions.
        </div>
      ) : viewMode === "chart" ? (
        <div className="bar-chart">
          {stats.map((stat, idx) => {
            const pct = getPercentage(stat.median_value);
            const isBest = stat.median_value === bestValue;
            return (
              <div key={idx} className={`bar-row ${isBest ? "best" : ""}`}>
                <div className="bar-rank">{idx + 1}</div>
                <div className="bar-label">
                  <span className="bar-hostname">{getLabel(stat)}</span>
                  <span className="bar-cpu">
                    n={stat.sample_count} | {stat.architecture}
                  </span>
                </div>
                <div className="bar-container">
                  <div
                    className="bar-fill"
                    style={{ width: `${getBarWidth(stat.median_value)}%` }}
                  />
                  <span className="bar-value">
                    {formatValue(stat.median_value)} {unit}
                    {pct && <span className="bar-pct"> ({pct})</span>}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <table className="results-table">
          <thead>
            <tr>
              <th>#</th>
              <th>{groupBy === "cpu" ? "CPU" : groupBy === "system" ? "System" : "Architecture"}</th>
              <th>Arch</th>
              <th className="value-col">Median</th>
              <th className="value-col">Mean</th>
              <th className="value-col">Min</th>
              <th className="value-col">Max</th>
              <th>Samples</th>
              <th>vs Best</th>
            </tr>
          </thead>
          <tbody>
            {stats.map((stat, idx) => {
              const pct = getPercentage(stat.median_value);
              const isBest = stat.median_value === bestValue;
              return (
                <tr key={idx} className={isBest ? "best-row" : ""}>
                  <td>{idx + 1}</td>
                  <td>{getLabel(stat)}</td>
                  <td>{stat.architecture}</td>
                  <td className={`value-col ${isBest ? "best" : ""}`}>
                    {formatValue(stat.median_value)}
                  </td>
                  <td className="value-col">{formatValue(stat.mean_value)}</td>
                  <td className="value-col">{formatValue(stat.min_value)}</td>
                  <td className="value-col">{formatValue(stat.max_value)}</td>
                  <td>{stat.sample_count}</td>
                  <td className={`pct-col ${pct ? "slower" : ""}`}>{pct || "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      {onViewFull && stats.length > 0 && (
        <div className="stats-footer">
          <span
            className="stats-full-link"
            onClick={() => onViewFull(testName)}
          >
            View all individual results →
          </span>
        </div>
      )}
    </div>
  );
}

export default StatsView;
