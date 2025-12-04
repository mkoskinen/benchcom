-- BENCHCOM Database Schema

-- Users table for authentication
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT users_username_key UNIQUE (username),
    CONSTRAINT users_email_key UNIQUE (email)
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);

-- Main benchmark runs table
CREATE TABLE IF NOT EXISTS benchmark_runs (
    id SERIAL PRIMARY KEY,
    hostname VARCHAR(255),
    architecture VARCHAR(50),
    cpu_model VARCHAR(255),
    cpu_cores INTEGER,
    total_memory_mb INTEGER,
    os_info TEXT,
    kernel_version VARCHAR(255),

    -- Timestamps
    benchmark_started_at TIMESTAMP,
    benchmark_completed_at TIMESTAMP,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- User relationship (NULL for anonymous submissions)
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,

    -- Metadata
    is_anonymous BOOLEAN DEFAULT FALSE,
    benchmark_version VARCHAR(50) DEFAULT '1.0',
    run_type_version INTEGER DEFAULT 1,
    labels TEXT[],
    tags JSONB,
    notes TEXT,

    -- Submitter info
    submitter_ip VARCHAR(45),
    dmi_info JSONB,

    -- Full console output from the benchmark run
    console_output TEXT
);

CREATE INDEX idx_benchmark_runs_hostname ON benchmark_runs(hostname);
CREATE INDEX idx_benchmark_runs_architecture ON benchmark_runs(architecture);
CREATE INDEX idx_benchmark_runs_submitted_at ON benchmark_runs(submitted_at);
CREATE INDEX idx_benchmark_runs_user_id ON benchmark_runs(user_id);
CREATE INDEX idx_benchmark_runs_tags ON benchmark_runs USING GIN(tags);
CREATE INDEX idx_benchmark_runs_labels ON benchmark_runs USING GIN(labels);
CREATE INDEX idx_benchmark_runs_run_type_version ON benchmark_runs(run_type_version);

-- Individual benchmark test results
CREATE TABLE IF NOT EXISTS benchmark_results (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES benchmark_runs(id) ON DELETE CASCADE,

    -- Test identification
    test_name VARCHAR(255) NOT NULL,
    test_category VARCHAR(100),

    -- Results
    value DOUBLE PRECISION,
    unit VARCHAR(50),
    raw_output TEXT,

    -- Additional metrics (flexible JSON structure)
    metrics JSONB
);

CREATE INDEX idx_benchmark_results_run_id ON benchmark_results(run_id);
CREATE INDEX idx_benchmark_results_test_name ON benchmark_results(test_name);
CREATE INDEX idx_benchmark_results_test_category ON benchmark_results(test_category);
CREATE INDEX idx_benchmark_results_metrics ON benchmark_results USING GIN(metrics);

-- View for common queries with aggregated data
CREATE OR REPLACE VIEW benchmark_summary AS
SELECT
    br.id,
    br.hostname,
    br.architecture,
    br.cpu_model,
    br.cpu_cores,
    br.submitted_at,
    br.is_anonymous,
    br.benchmark_version,
    br.run_type_version,
    br.labels,
    u.username,
    COUNT(bres.id) as result_count
FROM benchmark_runs br
LEFT JOIN users u ON br.user_id = u.id
LEFT JOIN benchmark_results bres ON br.id = bres.run_id
GROUP BY br.id, u.username;

-- Aggregated benchmark statistics table
-- Pre-computed median/mean/etc per CPU, architecture, system type, and test
CREATE TABLE IF NOT EXISTS benchmark_stats (
    id SERIAL PRIMARY KEY,

    -- Grouping keys
    cpu_model VARCHAR(255),
    architecture VARCHAR(50) NOT NULL,
    system_type VARCHAR(255),  -- from dmi_info (manufacturer + product)
    test_name VARCHAR(255) NOT NULL,
    test_category VARCHAR(100),
    unit VARCHAR(50),

    -- Statistics
    median_value DOUBLE PRECISION,
    mean_value DOUBLE PRECISION,
    min_value DOUBLE PRECISION,
    max_value DOUBLE PRECISION,
    stddev_value DOUBLE PRECISION,
    sample_count INTEGER NOT NULL DEFAULT 0,

    -- Metadata
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT benchmark_stats_unique UNIQUE(cpu_model, architecture, system_type, test_name)
);

CREATE INDEX IF NOT EXISTS idx_benchmark_stats_test_name ON benchmark_stats(test_name);
CREATE INDEX IF NOT EXISTS idx_benchmark_stats_cpu_model ON benchmark_stats(cpu_model);
CREATE INDEX IF NOT EXISTS idx_benchmark_stats_architecture ON benchmark_stats(architecture);
CREATE INDEX IF NOT EXISTS idx_benchmark_stats_system_type ON benchmark_stats(system_type);
CREATE INDEX IF NOT EXISTS idx_benchmark_stats_test_category ON benchmark_stats(test_category);
