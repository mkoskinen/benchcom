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
from typing import Optional, List, Dict, Any, Tuple

# Version info
BENCHCOM_VERSION = "1.1"


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
        api_username: Optional[str] = None,
        api_password: Optional[str] = None,
        fast: bool = False,
        full: bool = False,
    ):
        self.hostname = socket.gethostname()
        self.start_time = datetime.now(timezone.utc)
        self.cores = os.cpu_count() or 1
        self.results: List[BenchmarkResult] = []
        self.api_url = api_url
        self.api_token = api_token
        self.api_username = api_username
        self.api_password = api_password
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

    def run_command(self, cmd: List[str], timeout: int = 300) -> Tuple[str, int]:
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

    def get_openssl_cmd(self) -> Optional[str]:
        """Get the OpenSSL command path, preferring real OpenSSL over LibreSSL on macOS"""
        if platform.system() == "Darwin":
            # On macOS, prefer Homebrew OpenSSL over system LibreSSL
            # Check common Homebrew paths
            brew_paths = [
                "/opt/homebrew/opt/openssl@3/bin/openssl",  # Apple Silicon
                "/opt/homebrew/opt/openssl/bin/openssl",
                "/usr/local/opt/openssl@3/bin/openssl",     # Intel Mac
                "/usr/local/opt/openssl/bin/openssl",
            ]
            for path in brew_paths:
                if os.path.exists(path):
                    return path
        # Fall back to system openssl
        if self.check_command("openssl"):
            return "openssl"
        return None

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

        # Get version - 7z uses different version flags
        # Try running without args to get version from header
        version_output, _ = self.run_command([cmd_7z])
        if version_output:
            # Look for version line like "7-Zip [64] 17.05" or "p7zip Version 17.05"
            match = re.search(r"(?:7-Zip|p7zip)[^\d]*(\d+\.\d+)", version_output)
            if match:
                self.tool_versions["7zip"] = f"7-Zip {match.group(1)}"

        # Single thread
        self.log("=== 7-ZIP BENCHMARK (1 thread) ===")
        output, ret = self.run_command([cmd_7z, "b", "-mmt1"], timeout=120)
        if output and ret == 0:
            with open(self.output_dir / "7zip_1t.txt", "w") as f:
                f.write(output)

            # Extract MIPS from "Avr:" line (format: "Avr:   12345   12345   12345")
            # or "Tot:" line for total
            match = re.search(r"(?:Avr|Tot):\s+\d+\s+\d+\s+(\d+)", output)
            if match:
                mips = float(match.group(1))
                self.add_result("7zip_st", "compression", mips, "MIPS", output)
                self.log(f"  Single-thread: {mips:.0f} MIPS")
        elif ret != 0:
            self.log(f"  7zip benchmark failed (exit code {ret})")

        # Multi-thread (all cores) - use consistent name regardless of core count
        self.log(f"=== 7-ZIP BENCHMARK ({self.cores} threads) ===")
        output, ret = self.run_command([cmd_7z, "b", f"-mmt{self.cores}"], timeout=120)
        if output and ret == 0:
            with open(self.output_dir / f"7zip_{self.cores}t.txt", "w") as f:
                f.write(output)

            match = re.search(r"(?:Avr|Tot):\s+\d+\s+\d+\s+(\d+)", output)
            if match:
                mips = float(match.group(1))
                self.add_result("7zip_mt", "compression", mips, "MIPS", output,
                               metrics={"threads": self.cores})
                self.log(f"  Multi-thread ({self.cores}): {mips:.0f} MIPS")
        elif ret != 0:
            self.log(f"  7zip benchmark failed (exit code {ret})")

        self.log("")

    def run_zstd(self):
        """Run zstd compression benchmark"""
        if not self.check_command("zstd"):
            self.log("zstd not found, skipping...")
            return

        # Get version
        version = self.get_tool_version("zstd")
        if version:
            self.tool_versions["zstd"] = version

        self.log("=== ZSTD COMPRESSION BENCHMARK ===")

        # Create a test file with compressible data (pseudo-random but compressible)
        test_file = self.output_dir / "zstd_test_data"
        compressed_file = self.output_dir / "zstd_test_data.zst"

        try:
            # Generate 100MB of test data using /dev/urandom mixed with zeros
            # This creates data that's compressible but not trivially so
            import time

            with open(test_file, "wb") as f:
                # Write 100MB of data - mix of random and zeros for realistic compression
                for _ in range(100):
                    f.write(os.urandom(512 * 1024))  # 512KB random
                    f.write(b'\x00' * 512 * 1024)    # 512KB zeros

            # Compression benchmark
            self.log("  Compressing 100MB test file...")
            start = time.time()
            output, ret = self.run_command(
                ["zstd", "-f", "-3", str(test_file), "-o", str(compressed_file)],
                timeout=120
            )
            compress_time = time.time() - start

            if ret == 0 and compressed_file.exists():
                file_size_mb = 100  # 100 MB test file
                compress_speed = file_size_mb / compress_time
                compressed_size = compressed_file.stat().st_size / (1024 * 1024)
                ratio = file_size_mb / compressed_size

                self.add_result(
                    "zstd_compress", "compression", compress_speed, "MB/s",
                    f"Compressed 100MB in {compress_time:.2f}s, ratio {ratio:.2f}x",
                    metrics={"ratio": round(ratio, 2), "level": 3}
                )
                self.log(f"  Compression: {compress_speed:.1f} MB/s (ratio {ratio:.1f}x)")

                # Decompression benchmark
                self.log("  Decompressing...")
                decompressed_file = self.output_dir / "zstd_test_decompressed"
                start = time.time()
                output, ret = self.run_command(
                    ["zstd", "-d", "-f", str(compressed_file), "-o", str(decompressed_file)],
                    timeout=120
                )
                decompress_time = time.time() - start

                if ret == 0:
                    decompress_speed = file_size_mb / decompress_time
                    self.add_result(
                        "zstd_decompress", "compression", decompress_speed, "MB/s",
                        f"Decompressed 100MB in {decompress_time:.2f}s"
                    )
                    self.log(f"  Decompression: {decompress_speed:.1f} MB/s")

                # Cleanup
                if decompressed_file.exists():
                    decompressed_file.unlink()
            else:
                self.log(f"  zstd compression failed (exit code {ret})")

        except Exception as e:
            self.log(f"  zstd benchmark error: {e}")
        finally:
            # Cleanup
            if test_file.exists():
                test_file.unlink()
            if compressed_file.exists():
                compressed_file.unlink()

        self.log("")

    def run_openssl(self):
        """Run OpenSSL benchmarks"""
        openssl_cmd = self.get_openssl_cmd()
        if not openssl_cmd:
            self.log("openssl not found, skipping...")
            return

        # Get version
        version = self.get_tool_version(openssl_cmd, "version")
        if version:
            self.tool_versions["openssl"] = version

        # SHA256
        self.log("=== OPENSSL SPEED (SHA256, single-threaded) ===")
        output, _ = self.run_command([openssl_cmd, "speed", "-elapsed", "sha256"])
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
        output, _ = self.run_command([openssl_cmd, "speed", "-elapsed", "aes-256-cbc"])
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

    def run_openssl_full(self):
        """Run additional OpenSSL benchmarks (full suite)"""
        openssl_cmd = self.get_openssl_cmd()
        if not openssl_cmd:
            return

        # SHA512
        self.log("=== OPENSSL SPEED (SHA512, single-threaded) ===")
        output, _ = self.run_command([openssl_cmd, "speed", "-elapsed", "sha512"])
        if output:
            with open(self.output_dir / "openssl_sha512.txt", "w") as f:
                f.write(output)
            self.log("\n".join(output.split("\n")[-5:]))

            # Extract 16KB throughput (last column)
            match = re.search(
                r"sha512\s+[\d.]+k\s+[\d.]+k\s+[\d.]+k\s+[\d.]+k\s+[\d.]+k\s+([\d.]+)k",
                output,
            )
            if match:
                speed = float(match.group(1))
                self.add_result("openssl_sha512", "cryptography", speed, "KB/s", output)

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
                self.add_result("sysbench_cpu_st", "cpu", eps, "events/sec", output)
                self.log(f"  Single-thread: {eps:.2f} events/sec")
            else:
                self.log("  Could not parse sysbench output")
        elif ret != 0:
            self.log(f"  sysbench failed (exit code {ret})")

        # Multi-thread (all cores) - use consistent name regardless of core count
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
                # Use "sysbench_cpu_mt" for all multi-thread results (comparable across systems)
                self.add_result("sysbench_cpu_mt", "cpu", eps, "events/sec", output,
                               metrics={"threads": self.cores})
                self.log(f"  Multi-thread ({self.cores}): {eps:.2f} events/sec")
            else:
                self.log("  Could not parse sysbench output")
        elif ret != 0:
            self.log(f"  sysbench failed (exit code {ret})")

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
                self.log(f"  Memory throughput: {speed:.2f} MiB/sec")
            else:
                self.log("  Could not parse sysbench output")
        elif ret != 0:
            self.log(f"  sysbench memory failed (exit code {ret})")

        self.log("")

    def run_passmark(self):
        """Run PassMark PerformanceTest"""
        # Platform-specific paths
        if platform.system() == "Darwin":
            # macOS: pt_mac CLI tool (installed by benchcom.sh to ~/.cache/benchcom)
            pt_paths = [
                # Primary install location (benchcom.sh installs here)
                str(Path.home() / ".cache/benchcom/pt_mac"),
                # Common install locations
                "/usr/local/bin/pt_mac",
                "/opt/homebrew/bin/pt_mac",
                # Downloads folder (user may have extracted here)
                str(Path.home() / "Downloads/PerformanceTest/pt_mac"),
                str(Path.home() / "Downloads/pt_mac"),
                # Desktop
                str(Path.home() / "Desktop/PerformanceTest/pt_mac"),
                str(Path.home() / "Desktop/pt_mac"),
                # Applications folder (CLI version)
                "/Applications/PerformanceTest/pt_mac",
                str(Path.home() / "Applications/PerformanceTest/pt_mac"),
                # Just try pt_mac in PATH
                "pt_mac",
            ]
        else:
            # Determine architecture-specific binary name
            arch = platform.machine()
            if arch == "aarch64":
                arch_binary = "PerformanceTest_Linux_ARM64"
            elif arch in ("armv7l", "armhf"):
                arch_binary = "PerformanceTest_Linux_ARM32"
            else:
                arch_binary = "PerformanceTest_Linux_x86-64"

            pt_paths = [
                f"/opt/passmark/PerformanceTest/{arch_binary}",
                f"/opt/passmark/{arch_binary}",
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
            if platform.system() == "Darwin":
                self.log("PassMark not found. Download pt_mac CLI from:")
                self.log("  https://www.passmark.com/products/pt_mac/")
                self.log("  Then place pt_mac in ~/Downloads/PerformanceTest/ or /usr/local/bin/")
            else:
                self.log("PassMark not found, skipping...")
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
                self.add_result("passmark_cpu_mt", "cpu", cpu_mark, "points", results_yaml)
                self.log(f"  CPU Mark: {cpu_mark:.0f}")

            # Memory Mark
            mem_mark = extract_value("SUMM_ME")
            if mem_mark and mem_mark > 0:
                self.add_result("passmark_memory", "memory", mem_mark, "points", results_yaml)
                self.log(f"  Memory Mark: {mem_mark:.0f}")

            # Disk Mark
            disk_mark = extract_value("SUMM_DISK")
            if disk_mark and disk_mark > 0:
                self.add_result("passmark_disk", "disk", disk_mark, "points", results_yaml)
                self.log(f"  Disk Mark: {disk_mark:.0f}")

            # Individual CPU tests
            cpu_single = extract_value("CPU_SINGLETHREAD")
            if cpu_single and cpu_single > 0:
                self.add_result("passmark_cpu_single", "cpu", cpu_single, "points", results_yaml)
                self.log(f"  CPU Single Thread: {cpu_single:.0f}")

            cpu_integer = extract_value("CPU_INTEGER_MATH")
            if cpu_integer and cpu_integer > 0:
                self.add_result("passmark_integer", "cpu", cpu_integer, "points", results_yaml)

            cpu_float = extract_value("CPU_FLOATINGPOINT_MATH")
            if cpu_float and cpu_float > 0:
                self.add_result("passmark_float", "cpu", cpu_float, "points", results_yaml)

            cpu_prime = extract_value("CPU_PRIME")
            if cpu_prime and cpu_prime > 0:
                self.add_result("passmark_prime", "cpu", cpu_prime, "points", results_yaml)

            cpu_encryption = extract_value("CPU_ENCRYPTION")
            if cpu_encryption and cpu_encryption > 0:
                self.add_result("passmark_encryption", "cryptography", cpu_encryption, "points", results_yaml)

            cpu_compression = extract_value("CPU_COMPRESSION")
            if cpu_compression and cpu_compression > 0:
                self.add_result("passmark_compression", "compression", cpu_compression, "points", results_yaml)

            cpu_physics = extract_value("CPU_PHYSICS")
            if cpu_physics and cpu_physics > 0:
                self.add_result("passmark_physics", "cpu", cpu_physics, "points", results_yaml)

            cpu_sse = extract_value("CPU_MATRIX_MULT_SSE")
            if cpu_sse and cpu_sse > 0:
                self.add_result("passmark_sse", "cpu", cpu_sse, "points", results_yaml)

            # Memory detail tests
            mem_read_cached = extract_value("ME_READ_CACHED")
            if mem_read_cached and mem_read_cached > 0:
                self.add_result("passmark_mem_read_cached", "memory", mem_read_cached, "MB/s", results_yaml)

            mem_read_uncached = extract_value("ME_READ_UNCACHED")
            if mem_read_uncached and mem_read_uncached > 0:
                self.add_result("passmark_mem_read_uncached", "memory", mem_read_uncached, "MB/s", results_yaml)

            mem_write = extract_value("ME_WRITE")
            if mem_write and mem_write > 0:
                self.add_result("passmark_mem_write", "memory", mem_write, "MB/s", results_yaml)

            mem_latency = extract_value("ME_LATENCY")
            if mem_latency and mem_latency > 0:
                self.add_result("passmark_mem_latency", "memory", mem_latency, "ns", results_yaml)

            mem_threaded = extract_value("ME_THREADED")
            if mem_threaded and mem_threaded > 0:
                self.add_result("passmark_mem_threaded", "memory", mem_threaded, "MB/s", results_yaml)

            # Disk detail tests
            disk_seq_read = extract_value("DISK_SEQ_READ")
            if disk_seq_read and disk_seq_read > 0:
                self.add_result("passmark_disk_seq_read", "disk", disk_seq_read, "MB/s", results_yaml)

            disk_seq_write = extract_value("DISK_SEQ_WRITE")
            if disk_seq_write and disk_seq_write > 0:
                self.add_result("passmark_disk_seq_write", "disk", disk_seq_write, "MB/s", results_yaml)

            disk_random_read = extract_value("DISK_RANDOM_SEEK_RW")
            if disk_random_read and disk_random_read > 0:
                self.add_result("passmark_disk_random", "disk", disk_random_read, "ops/s", results_yaml)

            self.log("PassMark complete")
        else:
            if ret == 127:
                self.log(f"PassMark: binary not executable or missing dependencies")
                self.log(f"  Binary path: {pt_cmd}")
                self.log(f"  Try running: ldd {pt_cmd}")
            else:
                self.log(f"PassMark: no results file found (return code: {ret})")
            if output:
                # Log first few lines of output for debugging
                output_lines = output.strip().split('\n')[:10]
                for line in output_lines:
                    self.log(f"  {line}")
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
            # macOS uses different dd syntax (no conv=fdatasync)
            if platform.system() == "Darwin":
                # Write file then sync
                dd_cmd = [
                    "dd",
                    "if=/dev/zero",
                    f"of={test_file}",
                    "bs=1m",  # macOS uses lowercase
                    "count=1024",
                ]
            else:
                dd_cmd = [
                    "dd",
                    "if=/dev/zero",
                    f"of={test_file}",
                    "bs=1M",
                    "count=1024",
                    "conv=fdatasync",
                ]

            output, ret = self.run_command(dd_cmd)

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
        # Try to find a readable disk device (platform-specific)
        if platform.system() == "Darwin":
            devices = ["/dev/disk0", "/dev/disk1", "/dev/rdisk0", "/dev/rdisk1"]
        else:
            devices = ["/dev/mmcblk0", "/dev/sda", "/dev/nvme0n1", "/dev/vda"]

        disk_dev = None
        for dev in devices:
            if Path(dev).exists() and os.access(dev, os.R_OK):
                disk_dev = dev
                break

        if not disk_dev:
            self.log("=== DISK READ TEST ===")
            self.log("Skipping: no readable disk device found (may need root)")
            self.log("")
            return

        self.log(f"=== DISK READ TEST (1GB from {disk_dev}) ===")

        # Try to drop caches (Linux only, may need root)
        subprocess.run(["sync"], capture_output=True)
        if platform.system() != "Darwin":
            try:
                with open("/proc/sys/vm/drop_caches", "w") as f:
                    f.write("3")
            except (IOError, PermissionError):
                pass
        else:
            # macOS: purge command needs root, skip silently
            pass

        # Platform-specific dd command
        if platform.system() == "Darwin":
            dd_cmd = [
                "dd",
                f"if={disk_dev}",
                "of=/dev/null",
                "bs=1m",  # macOS uses lowercase
                "count=1024",
            ]
        else:
            dd_cmd = [
                "dd",
                f"if={disk_dev}",
                "of=/dev/null",
                "bs=1M",
                "count=1024",
                "iflag=direct",
            ]

        output, _ = self.run_command(dd_cmd)

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

        # Get CPU model and memory (platform-specific)
        if platform.system() == "Darwin":
            # macOS: use sysctl and system_profiler
            try:
                output, ret = self.run_command(["sysctl", "-n", "machdep.cpu.brand_string"])
                if ret == 0 and output.strip():
                    info["cpu_model"] = output.strip()
                else:
                    # Apple Silicon doesn't have brand_string, use system_profiler
                    output, ret = self.run_command(
                        ["system_profiler", "SPHardwareDataType"], timeout=30
                    )
                    if ret == 0:
                        for line in output.split("\n"):
                            if "Chip:" in line:
                                info["cpu_model"] = line.split(":", 1)[1].strip()
                                break
                            elif "Processor Name:" in line:
                                info["cpu_model"] = line.split(":", 1)[1].strip()
                                break
            except (IOError, OSError):
                info["cpu_model"] = "unknown"

            # macOS memory
            try:
                output, ret = self.run_command(["sysctl", "-n", "hw.memsize"])
                if ret == 0 and output.strip():
                    info["total_memory_mb"] = int(output.strip()) // (1024 * 1024)
            except (ValueError, OSError):
                info["total_memory_mb"] = 0
        else:
            # Linux: use /proc/cpuinfo
            cpu_model = None
            hardware = None
            try:
                with open("/proc/cpuinfo", "r") as f:
                    for line in f:
                        if line.startswith("model name"):
                            cpu_model = line.split(":", 1)[1].strip()
                            break
                        elif line.startswith("Model"):
                            # ARM: "Model" field (e.g., "Raspberry Pi 4 Model B Rev 1.4")
                            cpu_model = line.split(":", 1)[1].strip()
                        elif line.startswith("Hardware"):
                            # ARM: Hardware field (e.g., "BCM2835")
                            hardware = line.split(":", 1)[1].strip()
            except (IOError, OSError):
                pass

            # Use model name, or fall back to Hardware, or device-tree model
            if cpu_model:
                info["cpu_model"] = cpu_model
            elif hardware:
                info["cpu_model"] = hardware
            else:
                # Try device-tree model (works for Raspberry Pi and other ARM boards)
                try:
                    with open("/proc/device-tree/model", "r") as f:
                        model = f.read().strip().rstrip('\x00')
                        if model:
                            info["cpu_model"] = model
                except (IOError, OSError):
                    info["cpu_model"] = "unknown"

            # Linux memory
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
        def clean_sudo_output(output: str) -> str:
            """Remove sudo warnings from output"""
            lines = output.strip().split('\n')
            # Filter out sudo warning lines
            clean_lines = [l for l in lines if not l.startswith('sudo:')]
            return '\n'.join(clean_lines).strip()

        if self.check_command("dmidecode"):
            output, ret = self.run_command(["sudo", "dmidecode", "-s", "system-manufacturer"])
            output = clean_sudo_output(output)
            if ret == 0 and output and "Permission denied" not in output:
                dmi["manufacturer"] = output

                output, _ = self.run_command(["sudo", "dmidecode", "-s", "system-product-name"])
                output = clean_sudo_output(output)
                if output:
                    dmi["product"] = output

                output, _ = self.run_command(["sudo", "dmidecode", "-s", "system-version"])
                output = clean_sudo_output(output)
                if output:
                    dmi["version"] = output

                output, _ = self.run_command(["sudo", "dmidecode", "-s", "baseboard-product-name"])
                output = clean_sudo_output(output)
                if output:
                    dmi["board"] = output

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

    def login_to_api(self) -> Optional[str]:
        """Login to API with username/password and return access token"""
        if not self.api_url or not self.api_username or not self.api_password:
            return None

        try:
            import requests
        except ImportError:
            self.log("✗ requests library not available for API login")
            return None

        self.log(f"Logging in as '{self.api_username}'...")

        try:
            response = requests.post(
                f"{self.api_url}/api/v1/login",
                json={"username": self.api_username, "password": self.api_password},
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token")
                if token:
                    self.log("✓ Login successful")
                    return token
                else:
                    self.log("✗ Login failed: no token in response")
            else:
                self.log(f"✗ Login failed (HTTP {response.status_code})")
                self.log(f"  Response: {response.text}")
        except Exception as e:
            self.log(f"✗ Login error: {e}")

        return None

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

        # If username/password provided, login to get token
        token = self.api_token
        if self.api_username and self.api_password:
            token = self.login_to_api()
            if not token and not self.api_token:
                # Login failed and no fallback token
                self.log("Continuing with anonymous submission...")

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
        if token:
            headers["Authorization"] = f"Bearer {token}"

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
            self.run_openssl_full()
            self.run_sysbench_cpu()
            self.run_sysbench_memory()
            self.run_7zip()
            self.run_zstd()
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
    parser.add_argument("--api-token", help="API authentication token (JWT)")
    parser.add_argument("--api-username", help="API username (alternative to --api-token)")
    parser.add_argument("--api-password", help="API password (use with --api-username)")
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
        api_username=args.api_username,
        api_password=args.api_password,
        fast=args.fast,
        full=args.full,
    )

    runner.run_all()


if __name__ == "__main__":
    main()
