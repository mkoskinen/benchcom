from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import json

# Size limits
MAX_HOSTNAME_LENGTH = 255
MAX_STRING_LENGTH = 1000
MAX_RAW_OUTPUT_LENGTH = 100_000  # 100KB per result
MAX_CONSOLE_OUTPUT_LENGTH = 500_000  # 500KB total
MAX_RESULTS_PER_SUBMISSION = 100
MAX_JSON_DEPTH = 5
MAX_JSON_SIZE = 50_000  # 50KB for JSON fields like tags, metrics


def validate_json_size(value: Optional[Dict], field_name: str) -> Optional[Dict]:
    """Validate JSON field size and depth"""
    if value is None:
        return None
    json_str = json.dumps(value)
    if len(json_str) > MAX_JSON_SIZE:
        raise ValueError(f"{field_name} exceeds maximum size of {MAX_JSON_SIZE} bytes")
    return value


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
    test_name: str = Field(..., min_length=1, max_length=100)
    test_category: str = Field(..., min_length=1, max_length=100)
    value: Optional[float] = None
    unit: Optional[str] = Field(None, max_length=50)
    raw_output: Optional[str] = Field(None, max_length=MAX_RAW_OUTPUT_LENGTH)
    metrics: Optional[Dict[str, Any]] = None

    @field_validator("metrics")
    @classmethod
    def validate_metrics(cls, v):
        return validate_json_size(v, "metrics")


class BenchmarkResultResponse(BaseModel):
    id: int
    test_name: str
    test_category: str
    value: Optional[float]
    unit: Optional[str]
    metrics: Optional[Dict[str, Any]]


class BenchmarkRunCreate(BaseModel):
    hostname: str = Field(..., min_length=1, max_length=MAX_HOSTNAME_LENGTH)
    architecture: str = Field(..., min_length=1, max_length=50)
    cpu_model: Optional[str] = Field(None, max_length=MAX_STRING_LENGTH)
    cpu_cores: Optional[int] = Field(None, ge=1, le=10000)
    total_memory_mb: Optional[int] = Field(None, ge=0, le=100_000_000)  # 100TB max
    os_info: Optional[str] = Field(None, max_length=MAX_STRING_LENGTH)
    kernel_version: Optional[str] = Field(None, max_length=MAX_STRING_LENGTH)
    benchmark_started_at: Optional[str] = None  # Accept as string, parse in endpoint
    benchmark_completed_at: Optional[str] = None  # Accept as string, parse in endpoint
    benchmark_version: str = Field("1.0", max_length=50)
    tags: Optional[Dict[str, Any]] = None
    notes: Optional[str] = Field(None, max_length=10000)
    dmi_info: Optional[Dict[str, str]] = None
    console_output: Optional[str] = Field(None, max_length=MAX_CONSOLE_OUTPUT_LENGTH)
    results: List[BenchmarkResultCreate] = Field(..., max_length=MAX_RESULTS_PER_SUBMISSION)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        return validate_json_size(v, "tags")

    @field_validator("dmi_info")
    @classmethod
    def validate_dmi_info(cls, v):
        return validate_json_size(v, "dmi_info")


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
