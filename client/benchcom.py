#!/usr/bin/env python3
"""
BENCHCOM - Universal Linux Benchmark Client
"""

import argparse
import json
import os
import platform
import re
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

# Version info
BENCHCOM_VERSION = "1.1"

# ASCII art logo
LOGO = r"""
██████╗ ███████╗███╗   ██╗ ██████╗██╗  ██╗ ██████╗ ██████╗ ███╗   ███╗
██╔══██╗██╔════╝████╗  ██║██╔════╝██║  ██║██╔════╝██╔═══██╗████╗ ████║
██████╔╝█████╗  ██╔██╗ ██║██║     ███████║██║     ██║   ██║██╔████╔██║
██╔══██╗██╔══╝  ██║╚██╗██║██║     ██╔══██║██║     ██║   ██║██║╚██╔╝██║
██████╔╝███████╗██║ ╚████║╚██████╗██║  ██║╚██████╗╚██████╔╝██║ ╚═╝ ██║
╚═════╝ ╚══════╝╚═╝  ╚═══╝ ╚═════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═╝     ╚═╝
"""


class BenchmarkResult:
    def __init__(
        self,
        test_name: str,
        test_category: str,
        value: float,
        unit: str,
        raw_output: str,
        metrics: Optional[Dict[str, Any]] = None,
    ):
        self.test_name = test_name
        self.test_category = test_category
        self.value = value
        self.unit = unit
        self.raw_output = raw_output
        self.metrics = metrics or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_name": self.test_name,
            "test_category": self.test_category,
            "value": self.value,
            "unit": self.unit,
            "raw_output": self.raw_output,
            "metrics": self.metrics if self.metrics else None,
        }


class BenchmarkRunner:
    def __init__(
        self,
        output_dir: Optional[str] = None,
        api_url: Optional[str] = None,
        api_token: Optional[str] = None,
        fast: bool = False,
        full: bool = False,
    ):
        self.hostname = socket.gethostname()
        self.start_time = datetime.now(timezone.utc)
        self.cores = os.cpu_count() or 1
        self.results: List[BenchmarkResult] = []
        self.api_url = api_url
        self.api_token = api_token
        self.fast = fast
        self.full = full
        self.tool_versions: Dict[str, str] = {}

        # Create output directory
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
            self.output_dir = Path(f"benchcom_{self.hostname}_{timestamp}")

        self.output_dir.mkdir(exist_ok=True)
        self.log_file = self.output_dir / "benchmark_summary.txt"
        self.console_log: List[str] = []

    def log(self, message: str, also_print: bool = True):
        """Log message to file and optionally print to console"""
        if also_print:
            print(message)
        self.console_log.append(message)
        with open(self.log_file, "a") as f:
            f.write(message + "\n")

    def run_command(self, cmd: List[str], timeout: int = 300) -> tuple[str, int]:
        """Run a command and return (output, return_code)"""
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
            return result.stdout + result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", -1
        except FileNotFoundError:
            return "", -1

    def check_command(self, cmd: str) -> bool:
        """Check if a command is available"""
        result = subprocess.run(
            ["which", cmd], capture_output=True
        )
        return result.returncode == 0

    def get_tool_version(self, cmd: str, version_arg: str = "--version") -> Optional[str]:
        """Get version string for a tool"""
        try:
            result = subprocess.run(
                [cmd, version_arg], capture_output=True, text=True, timeout=10
            )
            output = result.stdout + result.stderr
            # Return first non-empty line
            for line in output.strip().split("\n"):
                if line.strip():
                    return line.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        return None

    def add_result(
        self,
        test_name: str,
        test_category: str,
        value: float,
        unit: str,
        raw_output: str,
        metrics: Optional[Dict[str, Any]] = None,
    ):
        """Add a benchmark result"""
        result = BenchmarkResult(test_name, test_category, value, unit, raw_output, metrics)
        self.results.append(result)

    def run_7zip(self):
        """Run 7-Zip benchmark"""
        # Try different 7z binary names:
        # - 7z: p7zip on most distros
        # - 7za: p7zip standalone
        # - 7zz: 7zip package on Debian/Ubuntu
        cmd_7z = None
        for cmd in ["7z", "7za", "7zz"]:
            if self.check_command(cmd):
                cmd_7z = cmd
                break

        if not cmd_7z:
            self.log("7z not found, skipping...")
            return

        # Get version
        version = self.get_tool_version(cmd_7z)
        if version:
            self.tool_versions["7zip"] = version

        # Single thread
        self.log("=== 7-ZIP BENCHMARK (1 thread) ===")
        output, _ = self.run_command([cmd_7z, "b", "-mmt1"])
        if output:
            with open(self.output_dir / "7zip_1t.txt", "w") as f:
                f.write(output)

            # Extract MIPS from "Avr:" line
            match = re.search(r"Avr:\s+\d+\s+\d+\s+(\d+)", output)
            if match:
                mips = float(match.group(1))
                self.add_result("7zip_1t", "compression", mips, "MIPS", output)

        # Multi-thread
        self.log(f"=== 7-ZIP BENCHMARK ({self.cores} threads) ===")
        output, _ = self.run_command([cmd_7z, "b", f"-mmt{self.cores}"])
        if output:
            with open(self.output_dir / f"7zip_{self.cores}t.txt", "w") as f:
                f.write(output)

            match = re.search(r"Avr:\s+\d+\s+\d+\s+(\d+)", output)
            if match:
                mips = float(match.group(1))
                self.add_result(
                    f"7zip_{self.cores}t", "compression", mips, "MIPS", output
                )

        self.log("")

    def run_openssl(self):
        """Run OpenSSL benchmarks"""
        if not self.check_command("openssl"):
            self.log("openssl not found, skipping...")
            return

        # Get version
        version = self.get_tool_version("openssl", "version")
        if version:
            self.tool_versions["openssl"] = version

        # SHA256
        self.log("=== OPENSSL SPEED (SHA256, single-threaded) ===")
        output, _ = self.run_command(["openssl", "speed", "-elapsed", "sha256"])
        if output:
            with open(self.output_dir / "openssl_sha256.txt", "w") as f:
                f.write(output)
            self.log("\n".join(output.split("\n")[-5:]))

            # Extract 16KB throughput (last column)
            match = re.search(
                r"sha256\s+[\d.]+k\s+[\d.]+k\s+[\d.]+k\s+[\d.]+k\s+[\d.]+k\s+([\d.]+)k",
                output,
            )
            if match:
                speed = float(match.group(1))
                self.add_result("openssl_sha256", "cryptography", speed, "KB/s", output)

        self.log("")

        # AES-256-CBC
        self.log("=== OPENSSL SPEED (AES-256-CBC, single-threaded) ===")
        output, _ = self.run_command(["openssl", "speed", "-elapsed", "aes-256-cbc"])
        if output:
            with open(self.output_dir / "openssl_aes256.txt", "w") as f:
                f.write(output)
            self.log("\n".join(output.split("\n")[-5:]))

            match = re.search(
                r"aes-256-cbc\s+[\d.]+k\s+[\d.]+k\s+[\d.]+k\s+[\d.]+k\s+[\d.]+k\s+([\d.]+)k",
                output,
            )
            if match:
                speed = float(match.group(1))
                self.add_result("openssl_aes256", "cryptography", speed, "KB/s", output)

        self.log("")

    def run_sysbench_cpu(self):
        """Run sysbench CPU benchmark"""
        if not self.check_command("sysbench"):
            self.log("sysbench not found, skipping...")
            return

        # Get version
        version = self.get_tool_version("sysbench")
        if version:
            self.tool_versions["sysbench"] = version

        # Single thread
        self.log("=== SYSBENCH CPU (1 thread) ===")
        output, ret = self.run_command(
            ["sysbench", "cpu", "--threads=1", "--time=10", "run"]
        )
        if ret == 0 and output:
            with open(self.output_dir / "sysbench_cpu_1t.txt", "w") as f:
                f.write(output)

            # Extract events per second
            match = re.search(r"events per second:\s+([\d.]+)", output)
            if match:
                eps = float(match.group(1))
                self.add_result("sysbench_cpu_1t", "cpu", eps, "events/sec", output)

        # Multi-thread
        self.log(f"=== SYSBENCH CPU ({self.cores} threads) ===")
        output, ret = self.run_command(
            ["sysbench", "cpu", f"--threads={self.cores}", "--time=10", "run"]
        )
        if ret == 0 and output:
            with open(self.output_dir / f"sysbench_cpu_{self.cores}t.txt", "w") as f:
                f.write(output)

            match = re.search(r"events per second:\s+([\d.]+)", output)
            if match:
                eps = float(match.group(1))
                self.add_result(f"sysbench_cpu_{self.cores}t", "cpu", eps, "events/sec", output)

        self.log("")

    def run_sysbench_memory(self):
        """Run sysbench memory benchmark"""
        if not self.check_command("sysbench"):
            return

        self.log("=== SYSBENCH MEMORY ===")
        output, ret = self.run_command(
            ["sysbench", "memory", "--memory-block-size=1K", "--memory-total-size=10G", "run"]
        )
        if ret == 0 and output:
            with open(self.output_dir / "sysbench_memory.txt", "w") as f:
                f.write(output)

            # Extract MiB/sec
            match = re.search(r"([\d.]+) MiB/sec", output)
            if match:
                speed = float(match.group(1))
                self.add_result("sysbench_memory", "memory", speed, "MiB/sec", output)

        self.log("")

    def run_passmark(self):
        """Run PassMark PerformanceTest Linux"""
        pt_paths = [
            "/opt/passmark/pt_linux/pt_linux",
            "/opt/passmark/PerformanceTest/PerformanceTest_Linux_x86-64",
            "/opt/passmark/PerformanceTest/PerformanceTest_Linux_ARM64",
            "/opt/passmark/PerformanceTest/pt_linux_x64",
            "/opt/passmark/pt_linux_x64",
            "/opt/passmark/pt_linux_arm64",
            "/usr/local/bin/pt_linux",
            "pt_linux",
        ]

        pt_cmd = None
        for path in pt_paths:
            if Path(path).exists():
                pt_cmd = path
                break
            if self.check_command(path):
                pt_cmd = path
                break

        if not pt_cmd:
            self.log("PassMark pt_linux not found, skipping...")
            return

        self.log("=== PASSMARK PERFORMANCETEST ===")
        self.log("Running PassMark (this may take several minutes)...")

        # Run PassMark - it outputs to results_cpu.yml in current directory
        # -r 1 = CPU only, -r 2 = Memory only, -r 3 = All
        output, ret = self.run_command([pt_cmd, "-r", "3"], timeout=900)

        # Find the results file (created in current working directory)
        results_files = list(Path.cwd().glob("results*.yml"))
        if not results_files:
            # Also check output directory
            results_files = list(self.output_dir.glob("results*.yml"))

        results_yaml = None
        for rf in results_files:
            try:
                results_yaml = rf.read_text()
                # Move results file to output directory
                dest = self.output_dir / rf.name
                if rf != dest:
                    rf.rename(dest)
                break
            except (IOError, OSError):
                continue

        if results_yaml:
            with open(self.output_dir / "passmark_raw.yml", "w") as f:
                f.write(results_yaml)

            # Parse YAML results (simple parsing without yaml library)
            def extract_value(key: str) -> Optional[float]:
                match = re.search(rf"{key}:\s*([\d.]+)", results_yaml)
                if match:
                    return float(match.group(1))
                return None

            # Get version info
            version_match = re.search(
                r"Major:\s*(\d+)\s+Minor:\s*(\d+)\s+Build:\s*(\d+)",
                results_yaml,
                re.DOTALL
            )
            if version_match:
                self.tool_versions["passmark"] = f"v{version_match.group(1)}.{version_match.group(2)} Build {version_match.group(3)}"

            # CPU Mark (overall CPU score)
            cpu_mark = extract_value("SUMM_CPU")
            if cpu_mark and cpu_mark > 0:
                self.add_result("passmark_cpu", "cpu", cpu_mark, "points", results_yaml)
                self.log(f"  CPU Mark: {cpu_mark:.0f}")

            # Memory Mark
            mem_mark = extract_value("SUMM_ME")
            if mem_mark and mem_mark > 0:
                self.add_result("passmark_memory", "memory", mem_mark, "points", results_yaml)
                self.log(f"  Memory Mark: {mem_mark:.0f}")

            # Individual CPU tests (store as metrics)
            cpu_tests = {
                "integer_math": extract_value("CPU_INTEGER_MATH"),
                "float_math": extract_value("CPU_FLOATINGPOINT_MATH"),
                "prime": extract_value("CPU_PRIME"),
                "sorting": extract_value("CPU_SORTING"),
                "encryption": extract_value("CPU_ENCRYPTION"),
                "compression": extract_value("CPU_COMPRESSION"),
                "single_thread": extract_value("CPU_SINGLETHREAD"),
                "physics": extract_value("CPU_PHYSICS"),
                "sse": extract_value("CPU_MATRIX_MULT_SSE"),
            }
            # Filter out None/zero values
            cpu_tests = {k: v for k, v in cpu_tests.items() if v}

            if cpu_tests:
                # Store single-thread score separately as it's useful for comparison
                st_score = cpu_tests.get("single_thread")
                if st_score:
                    self.add_result(
                        "passmark_cpu_single", "cpu", st_score, "points",
                        results_yaml, metrics=cpu_tests
                    )

            self.log("PassMark complete")
        else:
            self.log(f"PassMark: no results file found (return code: {ret})")
            if output:
                with open(self.output_dir / "passmark_output.txt", "w") as f:
                    f.write(output)

        self.log("")

    def run_pi_calculation(self):
        """Run Pi calculation benchmark"""
        if not self.check_command("bc"):
            self.log("bc not found, skipping pi calculation...")
            return

        self.log("=== SIMPLE CPU TEST (calculating pi) ===")
        import time

        start = time.time()

        proc = subprocess.Popen(
            ["bc", "-l"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        proc.communicate(input="scale=5000; 4*a(1)\n")

        elapsed = time.time() - start
        message = f"Time to calculate 5000 digits of Pi: {elapsed:.9f}s"
        self.log(message)
        self.add_result("pi_calculation", "cpu", elapsed, "seconds", message)
        self.log("")

    def run_disk_write(self):
        """Run disk write benchmark"""
        self.log("=== DISK WRITE TEST (1GB) ===")

        # Use home directory to avoid tmpfs, fall back to current dir
        home = Path.home()
        if home.exists():
            test_file = home / ".benchcom_disk_test"
        else:
            test_file = Path.cwd() / ".benchcom_disk_test"

        self.log(f"Test file: {test_file}")

        try:
            output, ret = self.run_command(
                [
                    "dd",
                    "if=/dev/zero",
                    f"of={test_file}",
                    "bs=1M",
                    "count=1024",
                    "conv=fdatasync",
                ]
            )

            if ret != 0 or "No space left" in output:
                self.log("Skipping: not enough disk space")
                if test_file.exists():
                    test_file.unlink()
                self.log("")
                return

            if output:
                try:
                    with open(self.output_dir / "disk_write.txt", "w") as f:
                        f.write(output)
                except OSError:
                    pass  # Ignore write errors for log file
                self.log(output)

                # Extract MB/s or GB/s
                match = re.search(r"([\d.]+)\s+GB/s", output)
                if match:
                    speed = float(match.group(1)) * 1024  # Convert to MB/s
                    self.add_result("disk_write", "disk", speed, "MB/s", output)
                else:
                    match = re.search(r"([\d.]+)\s+MB/s", output)
                    if match:
                        speed = float(match.group(1))
                        self.add_result("disk_write", "disk", speed, "MB/s", output)
        except OSError as e:
            self.log(f"Skipping: {e}")
        finally:
            # Clean up test file
            if test_file.exists():
                try:
                    test_file.unlink()
                except OSError:
                    pass

        self.log("")

    def run_disk_read(self):
        """Run disk read benchmark"""
        # Try to find a readable disk device
        devices = ["/dev/mmcblk0", "/dev/sda", "/dev/nvme0n1", "/dev/vda"]
        disk_dev = None

        for dev in devices:
            if Path(dev).exists() and os.access(dev, os.R_OK):
                disk_dev = dev
                break

        if not disk_dev:
            self.log("No readable disk found for read test")
            return

        self.log(f"=== DISK READ TEST (1GB from {disk_dev}) ===")

        # Try to drop caches (may need root)
        subprocess.run(["sync"], capture_output=True)
        try:
            with open("/proc/sys/vm/drop_caches", "w") as f:
                f.write("3")
        except (IOError, PermissionError):
            pass

        output, _ = self.run_command(
            [
                "dd",
                f"if={disk_dev}",
                "of=/dev/null",
                "bs=1M",
                "count=1024",
                "iflag=direct",
            ]
        )

        if output:
            with open(self.output_dir / "disk_read.txt", "w") as f:
                f.write(output)
            self.log(output)

            # Extract MB/s or GB/s
            match = re.search(r"([\d.]+)\s+GB/s", output)
            if match:
                speed = float(match.group(1)) * 1024
                self.add_result("disk_read", "disk", speed, "MB/s", output)
            else:
                match = re.search(r"([\d.]+)\s+MB/s", output)
                if match:
                    speed = float(match.group(1))
                    self.add_result("disk_read", "disk", speed, "MB/s", output)

        self.log("")

    def get_system_info(self) -> Dict[str, Any]:
        """Get system information"""
        info = {
            "hostname": self.hostname,
            "architecture": platform.machine(),
            "cpu_cores": self.cores,
            "benchmark_version": BENCHCOM_VERSION,
        }

        # Get CPU model
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if line.startswith("model name"):
                        info["cpu_model"] = line.split(":", 1)[1].strip()
                        break
                    elif line.startswith("Hardware"):
                        info["cpu_model"] = line.split(":", 1)[1].strip()
                        break
        except (IOError, OSError):
            info["cpu_model"] = "unknown"

        # Get memory
        try:
            output, _ = self.run_command(["free", "-m"])
            match = re.search(r"Mem:\s+(\d+)", output)
            if match:
                info["total_memory_mb"] = int(match.group(1))
        except (ValueError, AttributeError):
            info["total_memory_mb"] = 0

        # Get kernel and OS info
        info["kernel_version"] = platform.release()
        info["os_info"] = " ".join(
            [
                platform.system(),
                self.hostname,
                platform.release(),
                platform.version(),
                platform.machine(),
            ]
        )

        # Get DMI/system info (requires root for some fields)
        dmi_info = self.get_dmi_info()
        if dmi_info:
            info["dmi_info"] = dmi_info

        return info

    def get_dmi_info(self) -> Optional[Dict[str, str]]:
        """Get DMI/SMBIOS system information"""
        dmi = {}

        # macOS: use system_profiler
        if platform.system() == "Darwin":
            output, ret = self.run_command(
                ["system_profiler", "SPHardwareDataType"], timeout=30
            )
            if ret == 0 and output:
                for line in output.split("\n"):
                    line = line.strip()
                    if line.startswith("Model Name:"):
                        dmi["product"] = line.split(":", 1)[1].strip()
                    elif line.startswith("Model Identifier:"):
                        dmi["version"] = line.split(":", 1)[1].strip()
                    elif line.startswith("Chip:"):
                        dmi["chip"] = line.split(":", 1)[1].strip()
                dmi["manufacturer"] = "Apple"
            return dmi if dmi else None

        # Linux: Try dmidecode first (most complete, but needs root)
        if self.check_command("dmidecode"):
            output, ret = self.run_command(["sudo", "dmidecode", "-s", "system-manufacturer"])
            if ret == 0 and output.strip() and "Permission denied" not in output:
                dmi["manufacturer"] = output.strip()

                output, _ = self.run_command(["sudo", "dmidecode", "-s", "system-product-name"])
                if output.strip():
                    dmi["product"] = output.strip()

                output, _ = self.run_command(["sudo", "dmidecode", "-s", "system-version"])
                if output.strip():
                    dmi["version"] = output.strip()

                output, _ = self.run_command(["sudo", "dmidecode", "-s", "baseboard-product-name"])
                if output.strip():
                    dmi["board"] = output.strip()

        # Fallback: try reading from /sys/class/dmi/id/ (no root needed)
        if not dmi:
            dmi_paths = {
                "manufacturer": "/sys/class/dmi/id/sys_vendor",
                "product": "/sys/class/dmi/id/product_name",
                "version": "/sys/class/dmi/id/product_version",
                "board": "/sys/class/dmi/id/board_name",
            }
            for key, path in dmi_paths.items():
                try:
                    with open(path, "r") as f:
                        value = f.read().strip()
                        if value and value not in ("To Be Filled By O.E.M.", "Default string", ""):
                            dmi[key] = value
                except (IOError, OSError, PermissionError):
                    pass

        # Fallback for ARM/embedded: try device-tree
        if not dmi:
            try:
                with open("/proc/device-tree/model", "r") as f:
                    model = f.read().strip().rstrip('\x00')
                    if model:
                        dmi["product"] = model
            except (IOError, OSError):
                pass

        return dmi if dmi else None

    def save_results(self):
        """Save results to JSON file"""
        results_file = self.output_dir / "results.json"
        data = {
            "benchcom_version": BENCHCOM_VERSION,
            "tool_versions": self.tool_versions,
            "results": [r.to_dict() for r in self.results],
        }

        with open(results_file, "w") as f:
            json.dump(data, f, indent=2)

        return results_file

    def submit_to_api(self, results_file: Path):
        """Submit results to API"""
        if not self.api_url:
            return

        try:
            import requests
        except ImportError:
            self.log("✗ requests library not available for API submission")
            return

        self.log("")
        self.log("================================")
        self.log(f"Submitting to API: {self.api_url}")
        self.log("================================")

        # Load results
        with open(results_file, "r") as f:
            results_data = json.load(f)

        # Get system info
        system_info = self.get_system_info()

        # Build payload
        end_time = datetime.now(timezone.utc)
        payload = {
            **system_info,
            "benchmark_started_at": self.start_time.isoformat(),
            "benchmark_completed_at": end_time.isoformat(),
            "tags": {
                "benchcom_version": BENCHCOM_VERSION,
                "tool_versions": self.tool_versions,
            },
            "console_output": "\n".join(self.console_log),
            "results": results_data["results"],
        }

        # Submit
        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        try:
            response = requests.post(
                f"{self.api_url}/api/v1/benchmarks",
                json=payload,
                headers=headers,
                timeout=30,
            )

            if response.status_code in (200, 201):
                self.log(
                    f"✓ Successfully submitted to API (HTTP {response.status_code})"
                )
                data = response.json()
                if "id" in data:
                    self.log(f"  Benchmark ID: {data['id']}")
            else:
                self.log(f"✗ API submission failed (HTTP {response.status_code})")
                self.log(f"  Response: {response.text}")
        except Exception as e:
            self.log(f"✗ API submission error: {e}")

    def run_all(self):
        """Run all benchmarks"""
        # Print logo
        for line in LOGO.strip().split('\n'):
            self.log(line)
        self.log("")
        self.log(f"v{BENCHCOM_VERSION} - Universal Benchmark Suite")
        if self.fast:
            self.log("(FAST MODE)")
        self.log(f"Hostname: {self.hostname}")
        self.log(f"Cores detected: {self.cores}")
        self.log(f"Started: {datetime.now()}")
        self.log("================================")
        self.log("")

        # System info
        self.log("=== SYSTEM INFO ===")
        self.log(f"{platform.system()} {platform.release()} {platform.machine()}")
        self.log("")

        # Run benchmarks
        if self.fast:
            # Fast mode: just openssl (usually available)
            self.run_openssl()
        elif self.full:
            # Full suite: everything
            self.run_passmark()
            self.run_openssl()
            self.run_sysbench_cpu()
            self.run_sysbench_memory()
            self.run_7zip()
            self.run_pi_calculation()
            self.run_disk_write()
            self.run_disk_read()
        else:
            # Default: PassMark (comprehensive) + OpenSSL (fallback if PassMark unavailable)
            self.run_passmark()
            self.run_openssl()

        # Log tool versions
        if self.tool_versions:
            self.log("=== TOOL VERSIONS ===")
            for tool, version in self.tool_versions.items():
                self.log(f"  {tool}: {version}")
            self.log("")

        # Save results
        self.log("================================")
        self.log("Benchmark Complete!")
        self.log(f"Finished: {datetime.now()}")
        self.log(f"Results saved to: {self.output_dir}/")
        self.log("================================")

        results_file = self.save_results()

        # Submit to API if configured
        if self.api_url:
            self.submit_to_api(results_file)

        # Create tarball
        try:
            tarball = f"{self.output_dir}.tar.gz"
            subprocess.run(
                ["tar", "-czf", tarball, str(self.output_dir)], capture_output=True
            )
            if Path(tarball).exists():
                size = subprocess.run(
                    ["du", "-h", tarball], capture_output=True, text=True
                ).stdout.split()[0]
                self.log("")
                self.log(f"Compressed results: {tarball}")
                self.log(f"Size: {size}")
        except (OSError, subprocess.SubprocessError, IndexError):
            pass


def main():
    parser = argparse.ArgumentParser(description=f"BENCHCOM v{BENCHCOM_VERSION} - Universal Linux Benchmark")
    parser.add_argument("--api-url", help="API URL to submit results to")
    parser.add_argument("--api-token", help="API authentication token")
    parser.add_argument("--output-dir", help="Output directory for results")
    parser.add_argument(
        "--fast", action="store_true", help="Fast mode: only run openssl (quick)"
    )
    parser.add_argument(
        "--full", action="store_true", help="Full mode: run all benchmarks (passmark, openssl, sysbench, 7zip, disk I/O)"
    )
    parser.add_argument(
        "--version", action="version", version=f"BENCHCOM v{BENCHCOM_VERSION}"
    )

    args = parser.parse_args()

    runner = BenchmarkRunner(
        output_dir=args.output_dir,
        api_url=args.api_url,
        api_token=args.api_token,
        fast=args.fast,
        full=args.full,
    )

    runner.run_all()


if __name__ == "__main__":
    main()
