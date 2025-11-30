export interface Benchmark {
  id: number;
  hostname: string;
  architecture: string;
  cpu_model: string | null;
  cpu_cores: number | null;
  total_memory_mb: number | null;
  submitted_at: string;
  is_anonymous: boolean;
  benchmark_version: string;
  username: string | null;
  result_count: number;
  dmi_info: Record<string, string> | null;
}

export interface BenchmarkDetail {
  id: number;
  hostname: string;
  architecture: string;
  cpu_model: string | null;
  cpu_cores: number | null;
  total_memory_mb: number | null;
  os_info: string | null;
  kernel_version: string | null;
  benchmark_started_at: string | null;
  benchmark_completed_at: string | null;
  submitted_at: string;
  is_anonymous: boolean;
  benchmark_version: string;
  tags: Record<string, any> | null;
  notes: string | null;
  dmi_info: Record<string, string> | null;
  username: string | null;
  results: BenchmarkResult[];
}

export interface BenchmarkResult {
  id: number;
  test_name: string;
  test_category: string;
  value: number | null;
  unit: string | null;
  metrics: Record<string, any> | null;
}

export interface TestInfo {
  test_name: string;
  test_category: string;
  unit: string | null;
  result_count: number;
}

export interface TestResult {
  id: number;
  test_name: string;
  test_category: string;
  value: number | null;
  unit: string | null;
  run_id: number;
  hostname: string;
  cpu_model: string | null;
  cpu_cores: number | null;
  architecture: string;
  submitted_at: string;
}
