import json
import logging
from datetime import timedelta, datetime
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import db
from .schemas import (
    UserCreate,
    UserResponse,
    Token,
    LoginRequest,
    BenchmarkRunCreate,
    BenchmarkRunResponse,
    BenchmarkRunDetail,
)
from .auth import (
    get_password_hash,
    authenticate_user,
    create_access_token,
    get_current_user,
    get_current_user_optional,
    require_auth_if_needed,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

MAX_LIMIT = 500  # Maximum allowed limit for pagination


# Helper functions
def parse_iso_datetime(dt_string: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime string, stripping timezone for PostgreSQL timestamp."""
    if not dt_string:
        return None
    try:
        dt = datetime.fromisoformat(dt_string.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None)
    except (ValueError, AttributeError):
        return None


def parse_jsonb_field(value) -> Optional[dict]:
    """Parse JSONB field that may be string or dict."""
    if not value:
        return None
    if isinstance(value, str):
        return json.loads(value)
    return value

app = FastAPI(title=settings.PROJECT_NAME)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    """Initialize database connection pool"""
    await db.connect()


@app.on_event("shutdown")
async def shutdown():
    """Close database connection pool"""
    await db.disconnect()


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "auth_mode": settings.AUTH_MODE}


# Authentication endpoints
@app.post(f"{settings.API_V1_PREFIX}/register", response_model=UserResponse)
async def register(user: UserCreate):
    """Register a new user"""
    # Check if user exists
    existing = await db.fetchrow(
        "SELECT id FROM users WHERE username = $1 OR email = $2",
        user.username,
        user.email,
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered",
        )

    # Create user
    hashed_password = get_password_hash(user.password)
    query = """
        INSERT INTO users (username, email, hashed_password)
        VALUES ($1, $2, $3)
        RETURNING id, username, email, is_active, is_admin, created_at
    """
    result = await db.fetchrow(query, user.username, user.email, hashed_password)
    return dict(result)


@app.post(f"{settings.API_V1_PREFIX}/login", response_model=Token)
async def login(credentials: LoginRequest):
    """Login and get access token"""
    user = await authenticate_user(credentials.username, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user["id"])}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get(f"{settings.API_V1_PREFIX}/me", response_model=UserResponse)
async def get_me(current_user=Depends(get_current_user)):
    """Get current user info"""
    return dict(current_user)


# Benchmark endpoints
@app.post(f"{settings.API_V1_PREFIX}/benchmarks", response_model=dict)
async def submit_benchmark(
    request: Request,
    benchmark: BenchmarkRunCreate,
    current_user=Depends(require_auth_if_needed),
):
    """Submit a new benchmark run"""
    # Insert benchmark run
    user_id = current_user["id"] if current_user else None
    is_anonymous = user_id is None

    # Get submitter IP
    submitter_ip = request.client.host if request.client else None
    # Check for X-Forwarded-For header (if behind proxy)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        submitter_ip = forwarded_for.split(",")[0].strip()

    tags_json = json.dumps(benchmark.tags) if benchmark.tags else None
    dmi_json = json.dumps(benchmark.dmi_info) if benchmark.dmi_info else None

    # Parse datetime strings
    started_at = parse_iso_datetime(benchmark.benchmark_started_at)
    completed_at = parse_iso_datetime(benchmark.benchmark_completed_at)

    run_query = """
        INSERT INTO benchmark_runs (
            hostname, architecture, cpu_model, cpu_cores, total_memory_mb,
            os_info, kernel_version, benchmark_started_at, benchmark_completed_at,
            user_id, is_anonymous, benchmark_version, tags, notes,
            submitter_ip, dmi_info, console_output
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13::jsonb, $14, $15, $16::jsonb, $17)
        RETURNING id
    """
    run_id = await db.fetchval(
        run_query,
        benchmark.hostname,
        benchmark.architecture,
        benchmark.cpu_model,
        benchmark.cpu_cores,
        benchmark.total_memory_mb,
        benchmark.os_info,
        benchmark.kernel_version,
        started_at,
        completed_at,
        user_id,
        is_anonymous,
        benchmark.benchmark_version,
        tags_json,
        benchmark.notes,
        submitter_ip,
        dmi_json,
        benchmark.console_output,
    )

    # Insert results
    for result in benchmark.results:
        metrics_json = json.dumps(result.metrics) if result.metrics else None
        result_query = """
            INSERT INTO benchmark_results (
                run_id, test_name, test_category, value, unit, raw_output, metrics
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
        """
        await db.execute(
            result_query,
            run_id,
            result.test_name,
            result.test_category,
            result.value,
            result.unit,
            result.raw_output,
            metrics_json,
        )

    # Refresh stats for this CPU/architecture/system combination
    # This is quick since it only updates stats for this specific grouping
    system_type = None
    if benchmark.dmi_info:
        parts = []
        if benchmark.dmi_info.get("manufacturer"):
            parts.append(benchmark.dmi_info["manufacturer"])
        if benchmark.dmi_info.get("product"):
            parts.append(benchmark.dmi_info["product"])
        system_type = " ".join(parts) if parts else "Unknown"

    try:
        await refresh_benchmark_stats(
            cpu_model=benchmark.cpu_model,
            architecture=benchmark.architecture,
            system_type=system_type,
        )
    except Exception as e:
        # Don't fail the submission if stats refresh fails
        logger.warning(f"Stats refresh failed: {e}")

    return {"id": run_id, "message": "Benchmark submitted successfully"}


@app.get(
    f"{settings.API_V1_PREFIX}/benchmarks", response_model=List[BenchmarkRunResponse]
)
async def list_benchmarks(
    limit: int = 50,
    offset: int = 0,
    architecture: Optional[str] = None,
    hostname: Optional[str] = None,
):
    """List benchmark runs"""
    limit = min(limit, MAX_LIMIT)  # Enforce max limit
    where_clauses = []
    params = []
    param_count = 1

    if architecture:
        where_clauses.append(f"br.architecture = ${param_count}")
        params.append(architecture)
        param_count += 1

    if hostname:
        where_clauses.append(f"br.hostname = ${param_count}")
        params.append(hostname)
        param_count += 1

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    query = f"""
        SELECT
            br.id,
            br.hostname,
            br.architecture,
            br.cpu_model,
            br.cpu_cores,
            br.total_memory_mb,
            br.submitted_at,
            br.is_anonymous,
            br.benchmark_version,
            br.dmi_info,
            u.username,
            COUNT(bres.id) as result_count
        FROM benchmark_runs br
        LEFT JOIN users u ON br.user_id = u.id
        LEFT JOIN benchmark_results bres ON br.id = bres.run_id
        {where_sql}
        GROUP BY br.id, u.username
        ORDER BY br.submitted_at DESC
        LIMIT ${param_count} OFFSET ${param_count + 1}
    """
    params.extend([limit, offset])

    rows = await db.fetch(query, *params)
    result = []
    for row in rows:
        row_dict = dict(row)
        row_dict["dmi_info"] = parse_jsonb_field(row_dict.get("dmi_info"))
        result.append(row_dict)
    return result


@app.get(
    f"{settings.API_V1_PREFIX}/benchmarks/{{benchmark_id}}",
    response_model=BenchmarkRunDetail,
)
async def get_benchmark(
    benchmark_id: int,
    current_user=Depends(get_current_user_optional),
):
    """Get detailed benchmark run"""
    # Get run details (including sensitive fields)
    run_query = """
        SELECT
            br.id,
            br.hostname,
            br.architecture,
            br.cpu_model,
            br.cpu_cores,
            br.total_memory_mb,
            br.os_info,
            br.kernel_version,
            br.benchmark_started_at,
            br.benchmark_completed_at,
            br.submitted_at,
            br.is_anonymous,
            br.benchmark_version,
            br.tags,
            br.notes,
            br.dmi_info,
            br.console_output,
            br.submitter_ip,
            br.user_id,
            u.username
        FROM benchmark_runs br
        LEFT JOIN users u ON br.user_id = u.id
        WHERE br.id = $1
    """
    run = await db.fetchrow(run_query, benchmark_id)
    if not run:
        raise HTTPException(status_code=404, detail="Benchmark not found")

    # Get results
    results_query = """
        SELECT id, test_name, test_category, value, unit, metrics
        FROM benchmark_results
        WHERE run_id = $1
        ORDER BY id
    """
    results = await db.fetch(results_query, benchmark_id)

    run_dict = dict(run)

    # Determine if user can see sensitive data
    # Admin can see everything, user can see their own submissions
    can_see_sensitive = False
    if current_user:
        is_admin = current_user.get("is_admin", False)
        is_owner = run_dict.get("user_id") == current_user.get("id")
        can_see_sensitive = is_admin or is_owner

    # Remove sensitive fields if user doesn't have permission
    if not can_see_sensitive:
        run_dict["submitter_ip"] = None
        run_dict["console_output"] = None
        # Keep user_id as None for non-privileged users
        run_dict["user_id"] = None

    # Parse JSONB fields
    run_dict["tags"] = parse_jsonb_field(run_dict.get("tags"))
    run_dict["dmi_info"] = parse_jsonb_field(run_dict.get("dmi_info"))

    # Parse metrics JSON for each result
    parsed_results = []
    for r in results:
        r_dict = dict(r)
        r_dict["metrics"] = parse_jsonb_field(r_dict.get("metrics"))
        parsed_results.append(r_dict)

    run_dict["results"] = parsed_results
    return run_dict


@app.get(f"{settings.API_V1_PREFIX}/results/by-test")
async def get_results_by_test(
    test_name: Optional[str] = None,
    test_category: Optional[str] = None,
    limit: int = 50,
):
    """Get results grouped by test, sorted by best value first"""
    limit = min(limit, MAX_LIMIT)  # Enforce max limit
    where_clauses = []
    params = []
    param_count = 1

    if test_name:
        where_clauses.append(f"bres.test_name = ${param_count}")
        params.append(test_name)
        param_count += 1

    if test_category:
        where_clauses.append(f"bres.test_category = ${param_count}")
        params.append(test_category)
        param_count += 1

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    query = f"""
        SELECT
            bres.id,
            bres.test_name,
            bres.test_category,
            bres.value,
            bres.unit,
            br.id as run_id,
            br.hostname,
            br.cpu_model,
            br.cpu_cores,
            br.architecture,
            br.submitted_at,
            br.dmi_info
        FROM benchmark_results bres
        JOIN benchmark_runs br ON bres.run_id = br.id
        {where_sql}
        ORDER BY
            CASE
                WHEN bres.unit ILIKE '%second%' THEN bres.value
                ELSE -bres.value
            END ASC NULLS LAST
        LIMIT ${param_count}
    """
    params.append(limit)

    rows = await db.fetch(query, *params)
    result = []
    for row in rows:
        row_dict = dict(row)
        row_dict["dmi_info"] = parse_jsonb_field(row_dict.get("dmi_info"))
        result.append(row_dict)
    return result


@app.get(f"{settings.API_V1_PREFIX}/tests")
async def get_available_tests():
    """Get list of available test names and categories"""
    query = """
        SELECT DISTINCT
            test_name,
            test_category,
            unit,
            COUNT(*) as result_count
        FROM benchmark_results
        GROUP BY test_name, test_category, unit
        ORDER BY test_category, test_name
    """
    rows = await db.fetch(query)
    return [dict(row) for row in rows]


# ============================================================================
# Benchmark Statistics (Aggregated/Median views)
# ============================================================================

async def refresh_benchmark_stats(
    cpu_model: Optional[str] = None,
    architecture: Optional[str] = None,
    system_type: Optional[str] = None,
):
    """
    Refresh benchmark_stats table with aggregated statistics.
    If filters provided, only refresh matching rows (for incremental updates).
    Otherwise, refresh all stats.
    """
    # Build WHERE clause for filtering which stats to refresh
    where_clauses = []
    params = []
    param_idx = 1

    if cpu_model is not None:
        where_clauses.append(f"r.cpu_model = ${param_idx}")
        params.append(cpu_model)
        param_idx += 1
    if architecture is not None:
        where_clauses.append(f"r.architecture = ${param_idx}")
        params.append(architecture)
        param_idx += 1
    if system_type is not None:
        where_clauses.append(
            f"COALESCE(CONCAT(r.dmi_info->>'manufacturer', ' ', r.dmi_info->>'product'), 'Unknown') = ${param_idx}"
        )
        params.append(system_type)
        param_idx += 1

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    # Upsert aggregated stats
    query = f"""
        INSERT INTO benchmark_stats (
            cpu_model, architecture, system_type, test_name, test_category, unit,
            median_value, mean_value, min_value, max_value, stddev_value, sample_count,
            last_updated
        )
        SELECT
            r.cpu_model,
            r.architecture,
            COALESCE(
                NULLIF(CONCAT(
                    COALESCE(r.dmi_info->>'manufacturer', ''),
                    CASE WHEN r.dmi_info->>'manufacturer' IS NOT NULL
                         AND r.dmi_info->>'product' IS NOT NULL THEN ' ' ELSE '' END,
                    COALESCE(r.dmi_info->>'product', '')
                ), ''),
                'Unknown'
            ) as system_type,
            br.test_name,
            br.test_category,
            br.unit,
            percentile_cont(0.5) WITHIN GROUP (ORDER BY br.value) as median_value,
            AVG(br.value) as mean_value,
            MIN(br.value) as min_value,
            MAX(br.value) as max_value,
            STDDEV(br.value) as stddev_value,
            COUNT(*) as sample_count,
            CURRENT_TIMESTAMP
        FROM benchmark_results br
        JOIN benchmark_runs r ON br.run_id = r.id
        {where_sql}
        {"AND" if where_sql else "WHERE"} br.value IS NOT NULL
        GROUP BY
            r.cpu_model,
            r.architecture,
            r.dmi_info->>'manufacturer',
            r.dmi_info->>'product',
            br.test_name,
            br.test_category,
            br.unit
        ON CONFLICT (cpu_model, architecture, system_type, test_name)
        DO UPDATE SET
            test_category = EXCLUDED.test_category,
            unit = EXCLUDED.unit,
            median_value = EXCLUDED.median_value,
            mean_value = EXCLUDED.mean_value,
            min_value = EXCLUDED.min_value,
            max_value = EXCLUDED.max_value,
            stddev_value = EXCLUDED.stddev_value,
            sample_count = EXCLUDED.sample_count,
            last_updated = CURRENT_TIMESTAMP
    """

    await db.execute(query, *params)


@app.post(f"{settings.API_V1_PREFIX}/stats/refresh")
async def trigger_stats_refresh():
    """Manually trigger a full stats refresh (admin use)"""
    await refresh_benchmark_stats()
    return {"status": "ok", "message": "Stats refreshed"}


@app.get(f"{settings.API_V1_PREFIX}/stats/by-test")
async def get_stats_by_test(
    test_name: str,
    group_by: str = "cpu",  # cpu, system, architecture
    architecture: Optional[str] = None,
    limit: int = 50,
):
    """
    Get aggregated statistics for a test, grouped by CPU, system, or architecture.
    Returns median values for comparison.
    """
    limit = min(limit, MAX_LIMIT)  # Enforce max limit
    # Validate group_by
    if group_by not in ("cpu", "system", "architecture"):
        group_by = "cpu"

    # Build query based on grouping
    if group_by == "cpu":
        select_extra = "cpu_model"
    elif group_by == "system":
        select_extra = "system_type"
    else:  # architecture
        select_extra = "architecture"

    where_clauses = ["test_name = $1"]
    params = [test_name]
    param_idx = 2

    if architecture:
        where_clauses.append(f"architecture = ${param_idx}")
        params.append(architecture)
        param_idx += 1

    where_sql = " AND ".join(where_clauses)

    query = f"""
        SELECT
            {select_extra},
            architecture,
            test_name,
            test_category,
            unit,
            median_value,
            mean_value,
            min_value,
            max_value,
            stddev_value,
            sample_count,
            last_updated
        FROM benchmark_stats
        WHERE {where_sql}
        ORDER BY
            CASE
                WHEN unit ILIKE '%second%' THEN median_value
                ELSE -median_value
            END ASC NULLS LAST
        LIMIT ${param_idx}
    """
    params.append(limit)

    rows = await db.fetch(query, *params)
    return [dict(row) for row in rows]


@app.get(f"{settings.API_V1_PREFIX}/stats/by-cpu")
async def get_stats_by_cpu(
    cpu_model: str,
    architecture: Optional[str] = None,
):
    """Get all test statistics for a specific CPU model"""
    where_clauses = ["cpu_model = $1"]
    params = [cpu_model]
    param_idx = 2

    if architecture:
        where_clauses.append(f"architecture = ${param_idx}")
        params.append(architecture)
        param_idx += 1

    where_sql = " AND ".join(where_clauses)

    query = f"""
        SELECT
            cpu_model,
            architecture,
            system_type,
            test_name,
            test_category,
            unit,
            median_value,
            mean_value,
            min_value,
            max_value,
            stddev_value,
            sample_count,
            last_updated
        FROM benchmark_stats
        WHERE {where_sql}
        ORDER BY test_category, test_name
    """

    rows = await db.fetch(query, *params)
    return [dict(row) for row in rows]


@app.get(f"{settings.API_V1_PREFIX}/stats/available-cpus")
async def get_available_cpus():
    """Get list of CPUs with stats available"""
    query = """
        SELECT DISTINCT
            cpu_model,
            architecture,
            SUM(sample_count) as total_samples,
            COUNT(DISTINCT test_name) as test_count
        FROM benchmark_stats
        WHERE cpu_model IS NOT NULL
        GROUP BY cpu_model, architecture
        ORDER BY total_samples DESC
    """
    rows = await db.fetch(query)
    return [dict(row) for row in rows]


@app.get(f"{settings.API_V1_PREFIX}/stats/available-systems")
async def get_available_systems():
    """Get list of system types with stats available"""
    query = """
        SELECT DISTINCT
            system_type,
            architecture,
            SUM(sample_count) as total_samples,
            COUNT(DISTINCT test_name) as test_count
        FROM benchmark_stats
        WHERE system_type IS NOT NULL AND system_type != 'Unknown'
        GROUP BY system_type, architecture
        ORDER BY total_samples DESC
    """
    rows = await db.fetch(query)
    return [dict(row) for row in rows]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
