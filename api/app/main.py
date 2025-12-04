import json
import logging
from datetime import timedelta, datetime
from typing import List, Optional, Tuple, Any

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
    require_auth_for_submission,
    require_auth_for_browsing,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

MAX_LIMIT = 500  # Maximum allowed limit for pagination


class QueryBuilder:
    """
    Safe SQL query builder that uses parameterized queries throughout.
    Prevents SQL injection by never interpolating user values into SQL strings.
    """

    # Whitelist of allowed column names for dynamic queries
    ALLOWED_COLUMNS = frozenset([
        "id", "hostname", "architecture", "cpu_model", "cpu_cores",
        "total_memory_mb", "os_info", "kernel_version", "benchmark_started_at",
        "benchmark_completed_at", "submitted_at", "is_anonymous", "benchmark_version",
        "tags", "notes", "dmi_info", "console_output", "submitter_ip", "user_id",
        "test_name", "test_category", "value", "unit", "raw_output", "metrics",
        "run_id", "median_value", "mean_value", "min_value", "max_value",
        "stddev_value", "sample_count", "last_updated", "system_type",
        "username", "result_count", "total_samples", "test_count"
    ])

    # Whitelist of allowed table aliases
    ALLOWED_ALIASES = frozenset(["br", "bres", "r", "u"])

    def __init__(self):
        self.params: List[Any] = []
        self.param_idx = 1

    def add_param(self, value: Any) -> str:
        """Add a parameter and return its placeholder."""
        placeholder = f"${self.param_idx}"
        self.params.append(value)
        self.param_idx += 1
        return placeholder

    def validate_column(self, column: str) -> str:
        """Validate and return a safe column name."""
        # Handle aliased columns like "br.architecture"
        if "." in column:
            parts = column.split(".", 1)
            if len(parts) == 2:
                alias, col = parts
                if alias not in self.ALLOWED_ALIASES:
                    raise ValueError(f"Invalid table alias: {alias}")
                if col not in self.ALLOWED_COLUMNS:
                    raise ValueError(f"Invalid column name: {col}")
                return column
        if column not in self.ALLOWED_COLUMNS:
            raise ValueError(f"Invalid column name: {column}")
        return column

    def build_where(self, conditions: List[Tuple[str, Any]]) -> str:
        """
        Build a WHERE clause from a list of (column, value) tuples.
        Returns empty string if no conditions.
        """
        if not conditions:
            return ""

        clauses = []
        for column, value in conditions:
            safe_column = self.validate_column(column)
            placeholder = self.add_param(value)
            clauses.append(f"{safe_column} = {placeholder}")

        return "WHERE " + " AND ".join(clauses)

    def get_params(self) -> List[Any]:
        """Get the list of parameters for the query."""
        return self.params


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
    return {
        "status": "healthy",
        "allow_anonymous_submissions": settings.ALLOW_ANONYMOUS_SUBMISSIONS,
        "allow_anonymous_browsing": settings.ALLOW_ANONYMOUS_BROWSING,
        "anonymous_admin": settings.ANONYMOUS_ADMIN,
    }


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
    current_user=Depends(require_auth_for_submission),
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
            user_id, is_anonymous, benchmark_version, run_type_version, labels, tags, notes,
            submitter_ip, dmi_info, console_output
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15::jsonb, $16, $17, $18::jsonb, $19)
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
        benchmark.run_type_version,
        benchmark.labels,
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
    _auth=Depends(require_auth_for_browsing),
):
    """List benchmark runs"""
    limit = min(limit, MAX_LIMIT)  # Enforce max limit

    # Build conditions using QueryBuilder for safe parameterized queries
    qb = QueryBuilder()
    conditions: List[Tuple[str, Any]] = []

    if architecture:
        conditions.append(("br.architecture", architecture))
    if hostname:
        conditions.append(("br.hostname", hostname))

    where_sql = qb.build_where(conditions)

    # Add limit and offset as parameters
    limit_placeholder = qb.add_param(limit)
    offset_placeholder = qb.add_param(offset)

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
            br.run_type_version,
            br.labels,
            br.dmi_info,
            u.username,
            COUNT(bres.id) as result_count
        FROM benchmark_runs br
        LEFT JOIN users u ON br.user_id = u.id
        LEFT JOIN benchmark_results bres ON br.id = bres.run_id
        {where_sql}
        GROUP BY br.id, u.username
        ORDER BY br.submitted_at DESC
        LIMIT {limit_placeholder} OFFSET {offset_placeholder}
    """

    rows = await db.fetch(query, *qb.get_params())
    result = []
    for row in rows:
        row_dict = dict(row)
        row_dict["dmi_info"] = parse_jsonb_field(row_dict.get("dmi_info"))
        result.append(row_dict)
    return result


@app.delete(f"{settings.API_V1_PREFIX}/benchmarks/{{benchmark_id}}")
async def delete_benchmark(
    benchmark_id: int,
    current_user=Depends(get_current_user),
):
    """Delete a benchmark run. Admins can delete any, users can delete their own."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to delete benchmarks",
        )

    # Get the benchmark to check ownership
    run = await db.fetchrow(
        "SELECT id, user_id FROM benchmark_runs WHERE id = $1",
        benchmark_id,
    )
    if not run:
        raise HTTPException(status_code=404, detail="Benchmark not found")

    # Check permission: admin can delete any, user can delete their own
    is_admin = current_user.get("is_admin", False)
    is_owner = run["user_id"] == current_user["id"]

    if not is_admin and not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own submissions",
        )

    # Delete results first (in case there's no cascade)
    await db.execute("DELETE FROM benchmark_results WHERE run_id = $1", benchmark_id)
    # Delete the run
    await db.execute("DELETE FROM benchmark_runs WHERE id = $1", benchmark_id)

    logger.info(f"Benchmark {benchmark_id} deleted by user {current_user['id']} (admin={is_admin})")

    return {"message": f"Benchmark {benchmark_id} deleted successfully"}


@app.get(
    f"{settings.API_V1_PREFIX}/benchmarks/{{benchmark_id}}",
    response_model=BenchmarkRunDetail,
)
async def get_benchmark(
    benchmark_id: int,
    current_user=Depends(require_auth_for_browsing),
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
            br.run_type_version,
            br.labels,
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
    # Anonymous users are admin if ANONYMOUS_ADMIN is set
    if settings.ANONYMOUS_ADMIN:
        can_see_sensitive = True
    elif current_user:
        is_admin = current_user.get("is_admin", False)
        is_owner = run_dict.get("user_id") == current_user.get("id")
        can_see_sensitive = is_admin or is_owner
    else:
        can_see_sensitive = False

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
    _auth=Depends(require_auth_for_browsing),
):
    """Get results grouped by test, sorted by best value first"""
    limit = min(limit, MAX_LIMIT)  # Enforce max limit

    # Build conditions using QueryBuilder for safe parameterized queries
    qb = QueryBuilder()
    conditions: List[Tuple[str, Any]] = []

    if test_name:
        conditions.append(("bres.test_name", test_name))
    if test_category:
        conditions.append(("bres.test_category", test_category))

    where_sql = qb.build_where(conditions)
    limit_placeholder = qb.add_param(limit)

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
        LIMIT {limit_placeholder}
    """

    rows = await db.fetch(query, *qb.get_params())
    result = []
    for row in rows:
        row_dict = dict(row)
        row_dict["dmi_info"] = parse_jsonb_field(row_dict.get("dmi_info"))
        result.append(row_dict)
    return result


@app.get(f"{settings.API_V1_PREFIX}/tests")
async def get_available_tests(_auth=Depends(require_auth_for_browsing)):
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
    # Build WHERE clause using safe parameterized queries
    qb = QueryBuilder()
    where_parts: List[str] = []

    if cpu_model is not None:
        placeholder = qb.add_param(cpu_model)
        where_parts.append(f"r.cpu_model = {placeholder}")
    if architecture is not None:
        placeholder = qb.add_param(architecture)
        where_parts.append(f"r.architecture = {placeholder}")
    if system_type is not None:
        # This expression is safe - it only uses column references, no user input in SQL
        placeholder = qb.add_param(system_type)
        where_parts.append(
            f"COALESCE(CONCAT(r.dmi_info->>'manufacturer', ' ', r.dmi_info->>'product'), 'Unknown') = {placeholder}"
        )

    # Build WHERE clause - always include br.value IS NOT NULL
    if where_parts:
        where_sql = "WHERE " + " AND ".join(where_parts) + " AND br.value IS NOT NULL"
    else:
        where_sql = "WHERE br.value IS NOT NULL"

    # Upsert aggregated stats - query structure is static, only values are parameterized
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

    await db.execute(query, *qb.get_params())


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
    _auth=Depends(require_auth_for_browsing),
):
    """
    Get aggregated statistics for a test, grouped by CPU, system, or architecture.
    Returns median values for comparison.
    """
    limit = min(limit, MAX_LIMIT)  # Enforce max limit

    # Validate group_by against whitelist (prevents SQL injection via column name)
    GROUP_BY_COLUMNS = {
        "cpu": "cpu_model",
        "system": "system_type",
        "architecture": "architecture",
    }
    if group_by not in GROUP_BY_COLUMNS:
        group_by = "cpu"
    select_extra = GROUP_BY_COLUMNS[group_by]

    # Build query using QueryBuilder for safe parameterized queries
    qb = QueryBuilder()

    # Build WHERE conditions
    test_name_placeholder = qb.add_param(test_name)
    where_parts = [f"test_name = {test_name_placeholder}"]

    if architecture:
        arch_placeholder = qb.add_param(architecture)
        where_parts.append(f"architecture = {arch_placeholder}")

    limit_placeholder = qb.add_param(limit)

    # select_extra is from whitelist, safe to interpolate
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
        WHERE {" AND ".join(where_parts)}
        ORDER BY
            CASE
                WHEN unit ILIKE '%second%' THEN median_value
                ELSE -median_value
            END ASC NULLS LAST
        LIMIT {limit_placeholder}
    """

    rows = await db.fetch(query, *qb.get_params())
    return [dict(row) for row in rows]


@app.get(f"{settings.API_V1_PREFIX}/stats/by-cpu")
async def get_stats_by_cpu(
    cpu_model: str,
    architecture: Optional[str] = None,
    _auth=Depends(require_auth_for_browsing),
):
    """Get all test statistics for a specific CPU model"""
    # Build query using QueryBuilder for safe parameterized queries
    qb = QueryBuilder()

    cpu_placeholder = qb.add_param(cpu_model)
    where_parts = [f"cpu_model = {cpu_placeholder}"]

    if architecture:
        arch_placeholder = qb.add_param(architecture)
        where_parts.append(f"architecture = {arch_placeholder}")

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
        WHERE {" AND ".join(where_parts)}
        ORDER BY test_category, test_name
    """

    rows = await db.fetch(query, *qb.get_params())
    return [dict(row) for row in rows]


@app.get(f"{settings.API_V1_PREFIX}/stats/available-cpus")
async def get_available_cpus(_auth=Depends(require_auth_for_browsing)):
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
async def get_available_systems(_auth=Depends(require_auth_for_browsing)):
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
