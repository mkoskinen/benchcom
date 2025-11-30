import { useState, useMemo } from "react";
import { Benchmark } from "../types";

const formatMemory = (mb: number | null): string => {
  if (mb === null) return "—";
  if (mb < 1024) return `${mb} MB`;
  return `${Math.round(mb / 1024)} GB`;
};

type SortField = "hostname" | "architecture" | "cpu_model" | "cpu_cores" | "total_memory_mb" | "result_count" | "submitted_at";
type SortDirection = "asc" | "desc";

interface BenchmarkListProps {
  benchmarks: Benchmark[];
  onSelect: (id: number) => void;
  selectedForCompare: number[];
  onToggleCompare: (id: number) => void;
}

function BenchmarkList({
  benchmarks,
  onSelect,
  selectedForCompare,
  onToggleCompare,
}: BenchmarkListProps) {
  const [sortField, setSortField] = useState<SortField>("submitted_at");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDirection("desc");
    }
  };

  const sortedBenchmarks = useMemo(() => {
    return [...benchmarks].sort((a, b) => {
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
  }, [benchmarks, sortField, sortDirection]);

  if (benchmarks.length === 0) {
    return <div className="empty">No benchmarks found.</div>;
  }

  const getSortIndicator = (field: SortField) => {
    if (sortField !== field) return "";
    return sortDirection === "asc" ? " ▲" : " ▼";
  };

  const formatDate = (dateString: string) => {
    const d = new Date(dateString);
    return (
      d.toLocaleDateString() +
      " " +
      d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    );
  };

  const cropHostname = (hostname: string) => {
    const dotIndex = hostname.indexOf(".");
    return dotIndex > 0 ? hostname.substring(0, dotIndex) : hostname;
  };

  const formatSystem = (dmi: Record<string, string> | null) => {
    if (!dmi) return "—";
    const parts = [];
    if (dmi.manufacturer && dmi.manufacturer !== "Unknown") {
      parts.push(dmi.manufacturer);
    }
    if (dmi.product && dmi.product !== "Unknown") {
      parts.push(dmi.product);
    }
    if (dmi.chip) {
      parts.push(dmi.chip);
    }
    return parts.length > 0 ? parts.join(" ") : "—";
  };

  return (
    <table className="benchmark-table">
      <thead>
        <tr>
          <th className="checkbox-col">Compare</th>
          <th className="sortable" onClick={() => handleSort("hostname")}>
            Hostname{getSortIndicator("hostname")}
          </th>
          <th>System</th>
          <th className="sortable" onClick={() => handleSort("architecture")}>
            Arch{getSortIndicator("architecture")}
          </th>
          <th className="sortable" onClick={() => handleSort("cpu_model")}>
            CPU{getSortIndicator("cpu_model")}
          </th>
          <th className="sortable" onClick={() => handleSort("cpu_cores")}>
            Cores{getSortIndicator("cpu_cores")}
          </th>
          <th className="sortable" onClick={() => handleSort("total_memory_mb")}>
            RAM{getSortIndicator("total_memory_mb")}
          </th>
          <th className="sortable" onClick={() => handleSort("result_count")}>
            Tests{getSortIndicator("result_count")}
          </th>
          <th className="sortable" onClick={() => handleSort("submitted_at")}>
            Submitted{getSortIndicator("submitted_at")}
          </th>
        </tr>
      </thead>
      <tbody>
        {sortedBenchmarks.map((benchmark) => {
          const isSelected = selectedForCompare.includes(benchmark.id);
          return (
            <tr key={benchmark.id} className={isSelected ? "selected" : ""}>
              <td className="checkbox-col">
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={() => onToggleCompare(benchmark.id)}
                />
              </td>
              <td className="clickable" onClick={() => onSelect(benchmark.id)}>
                <strong>{cropHostname(benchmark.hostname)}</strong>
              </td>
              <td className="clickable" onClick={() => onSelect(benchmark.id)}>
                {formatSystem(benchmark.dmi_info)}
              </td>
              <td className="clickable" onClick={() => onSelect(benchmark.id)}>
                {benchmark.architecture}
              </td>
              <td className="clickable" onClick={() => onSelect(benchmark.id)}>
                {benchmark.cpu_model || "—"}
              </td>
              <td className="clickable" onClick={() => onSelect(benchmark.id)}>
                {benchmark.cpu_cores || "—"}
              </td>
              <td className="clickable" onClick={() => onSelect(benchmark.id)}>
                {formatMemory(benchmark.total_memory_mb)}
              </td>
              <td className="clickable" onClick={() => onSelect(benchmark.id)}>
                {benchmark.result_count}
              </td>
              <td className="clickable" onClick={() => onSelect(benchmark.id)}>
                {formatDate(benchmark.submitted_at)}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export default BenchmarkList;
