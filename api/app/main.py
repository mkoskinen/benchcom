from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import timedelta, datetime
from typing import List, Optional
import json

from .config import settings
from .database import db
from .schemas import (
    UserCreate,
    UserResponse,
    Token,
    BenchmarkRunCreate,
    BenchmarkRunResponse,
    BenchmarkRunDetail,
)
from .auth import (
    get_password_hash,
    authenticate_user,
    create_access_token,
    get_current_user,
    require_auth_if_needed,
)

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
        RETURNING id, username, email, is_active, created_at
    """
    result = await db.fetchrow(query, user.username, user.email, hashed_password)
    return dict(result)


@app.post(f"{settings.API_V1_PREFIX}/login", response_model=Token)
async def login(username: str, password: str):
    """Login and get access token"""
    user = await authenticate_user(username, password)
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

    # Parse datetime strings if provided (strip timezone for PostgreSQL timestamp without time zone)
    started_at = None
    if benchmark.benchmark_started_at:
        try:
            dt = datetime.fromisoformat(
                benchmark.benchmark_started_at.replace("Z", "+00:00")
            )
            started_at = dt.replace(tzinfo=None)  # Strip timezone info
        except (ValueError, AttributeError):
            started_at = None

    completed_at = None
    if benchmark.benchmark_completed_at:
        try:
            dt = datetime.fromisoformat(
                benchmark.benchmark_completed_at.replace("Z", "+00:00")
            )
            completed_at = dt.replace(tzinfo=None)  # Strip timezone info
        except (ValueError, AttributeError):
            completed_at = None

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
            br.submitted_at,
            br.is_anonymous,
            br.benchmark_version,
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
    return [dict(row) for row in rows]


@app.get(
    f"{settings.API_V1_PREFIX}/benchmarks/{{benchmark_id}}",
    response_model=BenchmarkRunDetail,
)
async def get_benchmark(benchmark_id: int):
    """Get detailed benchmark run"""
    # Get run details
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
    # Parse tags from JSONB
    if run_dict.get("tags"):
        run_dict["tags"] = (
            json.loads(run_dict["tags"])
            if isinstance(run_dict["tags"], str)
            else run_dict["tags"]
        )
    # Parse dmi_info from JSONB
    if run_dict.get("dmi_info"):
        run_dict["dmi_info"] = (
            json.loads(run_dict["dmi_info"])
            if isinstance(run_dict["dmi_info"], str)
            else run_dict["dmi_info"]
        )

    run_dict["results"] = [dict(r) for r in results]
    return run_dict


@app.get(f"{settings.API_V1_PREFIX}/results/by-test")
async def get_results_by_test(
    test_name: Optional[str] = None,
    test_category: Optional[str] = None,
    limit: int = 50,
):
    """Get results grouped by test, sorted by best value first"""
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
            br.submitted_at
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
    return [dict(row) for row in rows]


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
