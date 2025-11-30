import { Benchmark } from "../types";

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
  if (benchmarks.length === 0) {
    return <div className="empty">No benchmarks found.</div>;
  }

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

  return (
    <table className="benchmark-table">
      <thead>
        <tr>
          <th className="checkbox-col">Compare</th>
          <th>Hostname</th>
          <th>Arch</th>
          <th>CPU</th>
          <th>Cores</th>
          <th>Tests</th>
          <th>Submitted</th>
        </tr>
      </thead>
      <tbody>
        {benchmarks.map((benchmark) => {
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
                {benchmark.architecture}
              </td>
              <td className="clickable" onClick={() => onSelect(benchmark.id)}>
                {benchmark.cpu_model || "—"}
              </td>
              <td className="clickable" onClick={() => onSelect(benchmark.id)}>
                {benchmark.cpu_cores || "—"}
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
