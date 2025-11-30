"""
API tests for BENCHCOM - tests submission and retrieval across architectures

Uses a separate test database and API instance to avoid polluting production data.
Requires: podman-compose --profile test up -d

Run with: make test
"""

import pytest
import httpx

# Test API runs on port 8001 with separate test database
BASE_URL = "http://localhost:8001"
API_PREFIX = "/api/v1"


# Sample benchmark data for different architectures
SAMPLE_BENCHMARKS = {
    "x86_64": {
        "hostname": "test-x86-server",
        "architecture": "x86_64",
        "cpu_model": "Intel Core i7-10700K",
        "cpu_cores": 8,
        "total_memory_mb": 32768,
        "os_info": "Fedora Linux 42",
        "kernel_version": "6.12.0-300.fc42.x86_64",
        "benchmark_version": "1.1",
        "dmi_info": {
            "manufacturer": "LENOVO",
            "product": "ThinkPad T490",
            "version": "ThinkPad T490",
        },
        "tags": {
            "tool_versions": {"openssl": "OpenSSL 3.2.0"},
            "benchcom_version": "1.1",
        },
        "results": [
            {
                "test_name": "passmark_cpu",
                "test_category": "cpu",
                "value": 25000.0,
                "unit": "score",
                "raw_output": "CPU Mark: 25000",
            },
            {
                "test_name": "openssl_aes256",
                "test_category": "cryptography",
                "value": 1500000.0,
                "unit": "bytes/sec",
                "raw_output": "aes-256-cbc 1500000.00k",
            },
        ],
    },
    "aarch64": {
        "hostname": "test-arm-server",
        "architecture": "aarch64",
        "cpu_model": "Apple M2",
        "cpu_cores": 8,
        "total_memory_mb": 16384,
        "os_info": "macOS 14.0",
        "kernel_version": "Darwin 23.0.0",
        "benchmark_version": "1.1",
        "dmi_info": {
            "manufacturer": "Apple",
            "product": "MacBook Air",
            "chip": "Apple M2",
        },
        "tags": {
            "tool_versions": {"openssl": "LibreSSL 3.3.6"},
            "benchcom_version": "1.1",
        },
        "results": [
            {
                "test_name": "openssl_aes256",
                "test_category": "cryptography",
                "value": 2000000.0,
                "unit": "bytes/sec",
                "raw_output": "aes-256-cbc 2000000.00k",
            },
        ],
    },
    "riscv64": {
        "hostname": "test-riscv-spacemit",
        "architecture": "riscv64",
        "cpu_model": "SpacemiT X60",
        "cpu_cores": 8,
        "total_memory_mb": 16384,
        "os_info": "Fedora Linux 42",
        "kernel_version": "6.12.0-0.rc0.20241001gitbf4f29c74521.5.fc42.riscv64",
        "benchmark_version": "1.1",
        "dmi_info": None,  # RISC-V boards often lack DMI
        "tags": {
            "tool_versions": {
                "openssl": "OpenSSL 3.4.1 11 Feb 2025 (Library: OpenSSL 3.4.1 11 Feb 2025)"
            },
            "benchcom_version": "1.1",
        },
        "results": [
            {
                "test_name": "openssl_aes256",
                "test_category": "cryptography",
                "value": 45000.0,
                "unit": "bytes/sec",
                "raw_output": "aes-256-cbc 45000.00k",
            },
            {
                "test_name": "openssl_sha256",
                "test_category": "cryptography",
                "value": 120000.0,
                "unit": "bytes/sec",
                "raw_output": "sha256 120000.00k",
            },
        ],
    },
    "armv7l": {
        "hostname": "test-raspberry-pi",
        "architecture": "armv7l",
        "cpu_model": "BCM2837",
        "cpu_cores": 4,
        "total_memory_mb": 1024,
        "os_info": "Raspbian GNU/Linux 11",
        "kernel_version": "5.15.0-1027-raspi",
        "benchmark_version": "1.1",
        "dmi_info": {"product": "Raspberry Pi 3 Model B"},
        "tags": {
            "tool_versions": {"openssl": "OpenSSL 1.1.1n"},
            "benchcom_version": "1.1",
        },
        "results": [
            {
                "test_name": "openssl_aes256",
                "test_category": "cryptography",
                "value": 25000.0,
                "unit": "bytes/sec",
                "raw_output": "aes-256-cbc 25000.00k",
            },
        ],
    },
}


@pytest.fixture
def client():
    """HTTP client for test API"""
    return httpx.Client(base_url=BASE_URL, timeout=30.0)


class TestHealthCheck:
    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "auth_mode" in data


class TestBenchmarkSubmission:
    @pytest.mark.parametrize("arch", ["x86_64", "aarch64", "riscv64", "armv7l"])
    def test_submit_benchmark(self, client, arch):
        """Test submitting benchmarks for different architectures"""
        benchmark_data = SAMPLE_BENCHMARKS[arch]
        response = client.post(f"{API_PREFIX}/benchmarks", json=benchmark_data)
        assert response.status_code == 200, f"Failed for {arch}: {response.text}"
        data = response.json()
        assert "id" in data
        assert data["message"] == "Benchmark submitted successfully"

    def test_submit_minimal_benchmark(self, client):
        """Test submitting a minimal benchmark with only required fields"""
        minimal = {
            "hostname": "test-minimal",
            "architecture": "x86_64",
            "results": [
                {
                    "test_name": "test",
                    "test_category": "test",
                    "value": 100.0,
                    "unit": "score",
                }
            ],
        }
        response = client.post(f"{API_PREFIX}/benchmarks", json=minimal)
        assert response.status_code == 200

    def test_submit_benchmark_with_null_dmi(self, client):
        """Test that null dmi_info is accepted (common on RISC-V/embedded)"""
        data = SAMPLE_BENCHMARKS["riscv64"].copy()
        data["hostname"] = "test-null-dmi"
        data["dmi_info"] = None
        response = client.post(f"{API_PREFIX}/benchmarks", json=data)
        assert response.status_code == 200

    def test_submit_benchmark_with_empty_results(self, client):
        """Test that empty results list is handled"""
        data = {
            "hostname": "test-empty-results",
            "architecture": "x86_64",
            "results": [],
        }
        response = client.post(f"{API_PREFIX}/benchmarks", json=data)
        # Should still accept - empty results might be valid for failed benchmarks
        assert response.status_code in [200, 422]


class TestBenchmarkRetrieval:
    def test_list_benchmarks(self, client):
        """Test listing all benchmarks"""
        response = client.get(f"{API_PREFIX}/benchmarks")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_benchmarks_with_pagination(self, client):
        """Test pagination parameters"""
        response = client.get(f"{API_PREFIX}/benchmarks?limit=5&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 5

    def test_list_benchmarks_filter_by_architecture(self, client):
        """Test filtering by architecture"""
        # Submit test data first
        client.post(f"{API_PREFIX}/benchmarks", json=SAMPLE_BENCHMARKS["riscv64"])

        response = client.get(f"{API_PREFIX}/benchmarks?architecture=riscv64")
        assert response.status_code == 200
        data = response.json()
        for item in data:
            assert item["architecture"] == "riscv64"

    def test_get_benchmark_detail(self, client):
        """Test getting detailed benchmark info"""
        # First submit one
        response = client.post(
            f"{API_PREFIX}/benchmarks", json=SAMPLE_BENCHMARKS["x86_64"]
        )
        assert response.status_code == 200
        benchmark_id = response.json()["id"]

        # Then retrieve it
        response = client.get(f"{API_PREFIX}/benchmarks/{benchmark_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == benchmark_id
        assert data["hostname"] == "test-x86-server"
        assert data["architecture"] == "x86_64"
        assert "results" in data
        assert len(data["results"]) > 0
        # Check tags is properly returned as dict
        if data.get("tags"):
            assert isinstance(data["tags"], dict)

    def test_get_benchmark_detail_riscv(self, client):
        """Test getting RISC-V benchmark detail (regression test for tags issue)"""
        response = client.post(
            f"{API_PREFIX}/benchmarks", json=SAMPLE_BENCHMARKS["riscv64"]
        )
        assert response.status_code == 200
        benchmark_id = response.json()["id"]

        response = client.get(f"{API_PREFIX}/benchmarks/{benchmark_id}")
        assert response.status_code == 200, f"Failed to get RISC-V detail: {response.text}"
        data = response.json()
        assert data["architecture"] == "riscv64"
        # Verify tags dict structure
        if data.get("tags"):
            assert isinstance(data["tags"], dict)
            assert "tool_versions" in data["tags"] or "benchcom_version" in data["tags"]

    def test_get_nonexistent_benchmark(self, client):
        """Test 404 for nonexistent benchmark"""
        response = client.get(f"{API_PREFIX}/benchmarks/999999")
        assert response.status_code == 404


class TestResultsEndpoints:
    def test_get_available_tests(self, client):
        """Test getting list of available test types"""
        response = client.get(f"{API_PREFIX}/tests")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_results_by_test(self, client):
        """Test getting results filtered by test name"""
        # First submit some data
        client.post(f"{API_PREFIX}/benchmarks", json=SAMPLE_BENCHMARKS["x86_64"])

        response = client.get(f"{API_PREFIX}/results/by-test?test_name=openssl_aes256")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_results_by_category(self, client):
        """Test getting results filtered by category"""
        response = client.get(f"{API_PREFIX}/results/by-test?test_category=cryptography")
        assert response.status_code == 200


class TestComparison:
    """Tests for comparing multiple benchmarks (used by frontend comparison feature)"""

    def test_compare_multiple_benchmarks(self, client):
        """Test fetching multiple benchmarks for comparison"""
        # Submit benchmarks for different architectures
        ids = []
        for arch in ["x86_64", "aarch64"]:
            data = SAMPLE_BENCHMARKS[arch].copy()
            data["hostname"] = f"compare-test-{arch}"
            response = client.post(f"{API_PREFIX}/benchmarks", json=data)
            assert response.status_code == 200
            ids.append(response.json()["id"])

        # Fetch each benchmark detail (as frontend comparison does)
        benchmarks = []
        for bid in ids:
            response = client.get(f"{API_PREFIX}/benchmarks/{bid}")
            assert response.status_code == 200
            benchmarks.append(response.json())

        # Verify we got both
        assert len(benchmarks) == 2
        assert benchmarks[0]["id"] != benchmarks[1]["id"]

        # Verify both have results we can compare
        assert "results" in benchmarks[0]
        assert "results" in benchmarks[1]

    def test_compare_same_test_different_arch(self, client):
        """Test comparing the same test across different architectures"""
        # Submit x86, arm, and riscv with same test
        ids = []
        for arch in ["x86_64", "aarch64", "riscv64"]:
            response = client.post(
                f"{API_PREFIX}/benchmarks", json=SAMPLE_BENCHMARKS[arch]
            )
            assert response.status_code == 200
            ids.append(response.json()["id"])

        # Fetch all and verify openssl_aes256 results exist
        for bid in ids:
            response = client.get(f"{API_PREFIX}/benchmarks/{bid}")
            assert response.status_code == 200
            data = response.json()
            test_names = [r["test_name"] for r in data["results"]]
            assert "openssl_aes256" in test_names

    def test_dmi_info_in_list_and_detail(self, client):
        """Test that dmi_info is returned in both list and detail views"""
        # Submit with dmi_info
        data = SAMPLE_BENCHMARKS["x86_64"].copy()
        data["hostname"] = "test-dmi-compare"
        response = client.post(f"{API_PREFIX}/benchmarks", json=data)
        assert response.status_code == 200
        benchmark_id = response.json()["id"]

        # Check list includes dmi_info
        response = client.get(f"{API_PREFIX}/benchmarks?hostname=test-dmi-compare")
        assert response.status_code == 200
        items = response.json()
        assert len(items) > 0
        assert "dmi_info" in items[0]
        assert items[0]["dmi_info"]["manufacturer"] == "LENOVO"

        # Check detail includes dmi_info
        response = client.get(f"{API_PREFIX}/benchmarks/{benchmark_id}")
        assert response.status_code == 200
        data = response.json()
        assert "dmi_info" in data
        assert data["dmi_info"]["manufacturer"] == "LENOVO"


class TestConsoleOutput:
    """Tests for console output storage"""

    def test_submit_with_console_output(self, client):
        """Test submitting benchmark with console output"""
        data = SAMPLE_BENCHMARKS["x86_64"].copy()
        data["hostname"] = "test-console-output"
        data["console_output"] = "=== BENCHCOM ===\nRunning tests...\nComplete!"
        response = client.post(f"{API_PREFIX}/benchmarks", json=data)
        assert response.status_code == 200
        benchmark_id = response.json()["id"]

        # Verify it's stored
        response = client.get(f"{API_PREFIX}/benchmarks/{benchmark_id}")
        assert response.status_code == 200
        data = response.json()
        assert "console_output" in data
        assert data["console_output"] == "=== BENCHCOM ===\nRunning tests...\nComplete!"

    def test_submit_without_console_output(self, client):
        """Test that console_output is optional"""
        data = SAMPLE_BENCHMARKS["x86_64"].copy()
        data["hostname"] = "test-no-console"
        # Don't include console_output
        response = client.post(f"{API_PREFIX}/benchmarks", json=data)
        assert response.status_code == 200
        benchmark_id = response.json()["id"]

        response = client.get(f"{API_PREFIX}/benchmarks/{benchmark_id}")
        assert response.status_code == 200
        data = response.json()
        assert data.get("console_output") is None

    def test_large_console_output(self, client):
        """Test storing large console output"""
        large_output = "\n".join([f"Line {i}: " + "x" * 100 for i in range(1000)])
        data = SAMPLE_BENCHMARKS["x86_64"].copy()
        data["hostname"] = "test-large-console"
        data["console_output"] = large_output
        response = client.post(f"{API_PREFIX}/benchmarks", json=data)
        assert response.status_code == 200


class TestEdgeCases:
    def test_special_characters_in_hostname(self, client):
        """Test hostname with special characters"""
        data = {
            "hostname": "test-server_01.local",
            "architecture": "x86_64",
            "results": [
                {"test_name": "test", "test_category": "test", "value": 1.0, "unit": "x"}
            ],
        }
        response = client.post(f"{API_PREFIX}/benchmarks", json=data)
        assert response.status_code == 200

    def test_unicode_in_cpu_model(self, client):
        """Test unicode characters in CPU model"""
        data = {
            "hostname": "test-unicode",
            "architecture": "x86_64",
            "cpu_model": "Intel® Core™ i9-13900K",
            "results": [
                {"test_name": "test", "test_category": "test", "value": 1.0, "unit": "x"}
            ],
        }
        response = client.post(f"{API_PREFIX}/benchmarks", json=data)
        assert response.status_code == 200

    def test_very_long_raw_output(self, client):
        """Test handling of long raw output"""
        long_output = "x" * 100000
        data = {
            "hostname": "test-long-output",
            "architecture": "x86_64",
            "results": [
                {
                    "test_name": "test",
                    "test_category": "test",
                    "value": 1.0,
                    "unit": "x",
                    "raw_output": long_output,
                }
            ],
        }
        response = client.post(f"{API_PREFIX}/benchmarks", json=data)
        assert response.status_code == 200

    def test_null_value_in_result(self, client):
        """Test result with null value (benchmark might fail to produce a score)"""
        data = {
            "hostname": "test-null-value",
            "architecture": "x86_64",
            "results": [
                {
                    "test_name": "failed_test",
                    "test_category": "test",
                    "value": None,
                    "unit": None,
                    "raw_output": "Benchmark failed to run",
                }
            ],
        }
        response = client.post(f"{API_PREFIX}/benchmarks", json=data)
        assert response.status_code == 200

    def test_metrics_json_structure(self, client):
        """Test complex metrics JSON structure"""
        data = {
            "hostname": "test-metrics",
            "architecture": "x86_64",
            "results": [
                {
                    "test_name": "complex_test",
                    "test_category": "test",
                    "value": 100.0,
                    "unit": "score",
                    "metrics": {
                        "sub_scores": {"read": 150, "write": 50},
                        "iterations": 1000,
                        "threads": [1, 2, 4, 8],
                        "nested": {"deep": {"value": True}},
                    },
                }
            ],
        }
        response = client.post(f"{API_PREFIX}/benchmarks", json=data)
        assert response.status_code == 200


class TestMetricsJsonParsing:
    """Tests for metrics JSONB parsing in detail endpoint (regression tests)"""

    def test_metrics_returned_as_dict_not_string(self, client):
        """Test that metrics JSONB is returned as dict, not JSON string

        Regression test: Previously metrics were returned as a JSON string
        which caused Pydantic validation to fail with 'Input should be a valid dictionary'
        """
        # Submit benchmark with metrics (like PassMark CPU details)
        data = {
            "hostname": "test-metrics-parsing",
            "architecture": "aarch64",
            "cpu_model": "Raspberry Pi 4",
            "cpu_cores": 4,
            "results": [
                {
                    "test_name": "passmark_cpu_single",
                    "test_category": "cpu",
                    "value": 483.67,
                    "unit": "points",
                    "metrics": {
                        "sse": 780.69,
                        "prime": 3.56,
                        "physics": 81.76,
                        "sorting": 3518.07,
                        "encryption": 78.18,
                        "float_math": 4499.44,
                        "compression": 8549.33,
                        "integer_math": 11689.62,
                        "single_thread": 483.67,
                    },
                }
            ],
        }
        response = client.post(f"{API_PREFIX}/benchmarks", json=data)
        assert response.status_code == 200
        benchmark_id = response.json()["id"]

        # Get detail - this should NOT fail with validation error
        response = client.get(f"{API_PREFIX}/benchmarks/{benchmark_id}")
        assert response.status_code == 200, f"Detail endpoint failed: {response.text}"

        detail = response.json()
        assert "results" in detail

        # Find the result with metrics
        result_with_metrics = None
        for r in detail["results"]:
            if r.get("metrics"):
                result_with_metrics = r
                break

        assert result_with_metrics is not None, "Result with metrics not found"

        # Verify metrics is a dict, not a string
        metrics = result_with_metrics["metrics"]
        assert isinstance(metrics, dict), f"metrics should be dict, got {type(metrics)}"
        assert "single_thread" in metrics
        assert metrics["single_thread"] == 483.67

    def test_multiple_results_with_and_without_metrics(self, client):
        """Test benchmark with mix of results - some with metrics, some without"""
        data = {
            "hostname": "test-mixed-metrics",
            "architecture": "x86_64",
            "results": [
                {
                    "test_name": "passmark_cpu",
                    "test_category": "cpu",
                    "value": 25000.0,
                    "unit": "points",
                    "metrics": None,  # No detailed metrics
                },
                {
                    "test_name": "passmark_cpu_single",
                    "test_category": "cpu",
                    "value": 3500.0,
                    "unit": "points",
                    "metrics": {
                        "integer_math": 50000,
                        "float_math": 40000,
                    },
                },
                {
                    "test_name": "openssl_sha256",
                    "test_category": "cryptography",
                    "value": 1500000.0,
                    "unit": "KB/s",
                    # No metrics field at all
                },
            ],
        }
        response = client.post(f"{API_PREFIX}/benchmarks", json=data)
        assert response.status_code == 200
        benchmark_id = response.json()["id"]

        # Get detail
        response = client.get(f"{API_PREFIX}/benchmarks/{benchmark_id}")
        assert response.status_code == 200

        detail = response.json()
        assert len(detail["results"]) == 3

        # Verify each result type
        for r in detail["results"]:
            if r["test_name"] == "passmark_cpu":
                assert r["metrics"] is None
            elif r["test_name"] == "passmark_cpu_single":
                assert isinstance(r["metrics"], dict)
                assert r["metrics"]["integer_math"] == 50000
            elif r["test_name"] == "openssl_sha256":
                assert r.get("metrics") is None


class TestRaspberryPiSupport:
    """Tests for Raspberry Pi and ARM board support"""

    def test_raspberry_pi_with_device_tree_model(self, client):
        """Test Raspberry Pi submission with device-tree model info"""
        data = {
            "hostname": "raspberrypi",
            "architecture": "aarch64",
            "cpu_model": "Raspberry Pi 4 Model B Rev 1.4",  # From /proc/device-tree/model
            "cpu_cores": 4,
            "total_memory_mb": 7820,
            "kernel_version": "6.12.47+rpt-rpi-v8",
            "dmi_info": {
                "product": "Raspberry Pi 4 Model B Rev 1.4",
            },
            "results": [
                {
                    "test_name": "passmark_cpu",
                    "test_category": "cpu",
                    "value": 624.05,
                    "unit": "points",
                }
            ],
        }
        response = client.post(f"{API_PREFIX}/benchmarks", json=data)
        assert response.status_code == 200
        benchmark_id = response.json()["id"]

        # Verify in list
        response = client.get(f"{API_PREFIX}/benchmarks?hostname=raspberrypi")
        assert response.status_code == 200
        items = response.json()
        assert len(items) > 0
        pi = items[0]
        assert pi["cpu_model"] == "Raspberry Pi 4 Model B Rev 1.4"
        assert pi["architecture"] == "aarch64"

        # Verify in detail
        response = client.get(f"{API_PREFIX}/benchmarks/{benchmark_id}")
        assert response.status_code == 200
        detail = response.json()
        assert detail["cpu_model"] == "Raspberry Pi 4 Model B Rev 1.4"
        assert detail["dmi_info"]["product"] == "Raspberry Pi 4 Model B Rev 1.4"

    def test_arm_board_without_cpu_model(self, client):
        """Test ARM board where CPU model detection fails"""
        data = {
            "hostname": "unknown-arm-board",
            "architecture": "aarch64",
            "cpu_model": None,  # CPU model detection failed
            "cpu_cores": 4,
            "dmi_info": {
                "product": "Some ARM SBC",
            },
            "results": [
                {
                    "test_name": "openssl_sha256",
                    "test_category": "cryptography",
                    "value": 50000.0,
                    "unit": "KB/s",
                }
            ],
        }
        response = client.post(f"{API_PREFIX}/benchmarks", json=data)
        assert response.status_code == 200
        benchmark_id = response.json()["id"]

        # Should still be retrievable
        response = client.get(f"{API_PREFIX}/benchmarks/{benchmark_id}")
        assert response.status_code == 200
        detail = response.json()
        assert detail["cpu_model"] is None
        assert detail["dmi_info"]["product"] == "Some ARM SBC"

    def test_total_memory_in_list_response(self, client):
        """Test that total_memory_mb is included in list response"""
        data = {
            "hostname": "test-memory-list",
            "architecture": "aarch64",
            "total_memory_mb": 8192,
            "results": [
                {"test_name": "test", "test_category": "test", "value": 1.0, "unit": "x"}
            ],
        }
        response = client.post(f"{API_PREFIX}/benchmarks", json=data)
        assert response.status_code == 200

        response = client.get(f"{API_PREFIX}/benchmarks?hostname=test-memory-list")
        assert response.status_code == 200
        items = response.json()
        assert len(items) > 0
        assert "total_memory_mb" in items[0]
        assert items[0]["total_memory_mb"] == 8192


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
