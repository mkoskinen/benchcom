from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# User schemas
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    is_admin: bool = False
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


# Benchmark schemas
class BenchmarkResultCreate(BaseModel):
    test_name: str
    test_category: str
    value: Optional[float] = None
    unit: Optional[str] = None
    raw_output: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None


class BenchmarkResultResponse(BaseModel):
    id: int
    test_name: str
    test_category: str
    value: Optional[float]
    unit: Optional[str]
    metrics: Optional[Dict[str, Any]]


class BenchmarkRunCreate(BaseModel):
    hostname: str
    architecture: str
    cpu_model: Optional[str] = None
    cpu_cores: Optional[int] = None
    total_memory_mb: Optional[int] = None
    os_info: Optional[str] = None
    kernel_version: Optional[str] = None
    benchmark_started_at: Optional[str] = None  # Accept as string, parse in endpoint
    benchmark_completed_at: Optional[str] = None  # Accept as string, parse in endpoint
    benchmark_version: str = "1.0"
    tags: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    dmi_info: Optional[Dict[str, str]] = None
    console_output: Optional[str] = None
    results: List[BenchmarkResultCreate]


class BenchmarkRunResponse(BaseModel):
    id: int
    hostname: str
    architecture: str
    cpu_model: Optional[str]
    cpu_cores: Optional[int]
    total_memory_mb: Optional[int]
    submitted_at: datetime
    is_anonymous: bool
    benchmark_version: str
    username: Optional[str]
    result_count: int
    dmi_info: Optional[Dict[str, str]]


class BenchmarkRunDetail(BaseModel):
    id: int
    hostname: str
    architecture: str
    cpu_model: Optional[str]
    cpu_cores: Optional[int]
    total_memory_mb: Optional[int]
    os_info: Optional[str]
    kernel_version: Optional[str]
    benchmark_started_at: Optional[datetime]
    benchmark_completed_at: Optional[datetime]
    submitted_at: datetime
    is_anonymous: bool
    benchmark_version: str
    tags: Optional[Dict[str, Any]]
    notes: Optional[str]
    dmi_info: Optional[Dict[str, str]]
    console_output: Optional[str]
    username: Optional[str]
    results: List[BenchmarkResultResponse]
    # Sensitive fields (only visible to admins or the submitter)
    submitter_ip: Optional[str] = None
    user_id: Optional[int] = None
