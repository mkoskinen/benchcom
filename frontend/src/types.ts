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
  run_type_version: number | null;
  labels: string[] | null;
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
  run_type_version: number | null;
  labels: string[] | null;
  tags: Record<string, any> | null;
  notes: string | null;
  dmi_info: Record<string, string> | null;
  console_output: string | null;
  username: string | null;
  results: BenchmarkResult[];
  // Sensitive fields (only visible to admins or the submitter)
  submitter_ip: string | null;
  user_id: number | null;
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
  dmi_info: Record<string, string> | null;
}

// Auth types
export interface User {
  id: number;
  username: string;
  email: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface RegisterCredentials {
  username: string;
  email: string;
  password: string;
}

// Stats types
export interface BenchmarkStat {
  cpu_model: string | null;
  architecture: string;
  system_type: string | null;
  test_name: string;
  test_category: string | null;
  unit: string | null;
  median_value: number | null;
  mean_value: number | null;
  min_value: number | null;
  max_value: number | null;
  stddev_value: number | null;
  sample_count: number;
  last_updated: string;
}

export interface AvailableCpu {
  cpu_model: string;
  architecture: string;
  total_samples: number;
  test_count: number;
}

export interface AvailableSystem {
  system_type: string;
  architecture: string;
  total_samples: number;
  test_count: number;
}
