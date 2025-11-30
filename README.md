# BENCHCOM

Cross-platform benchmark collection and comparison tool. Run benchmarks on any machine (Linux/macOS, x86_64/ARM/RISC-V), submit results to a central server, and compare performance across systems.

## Quick Start

```bash
# Start the server
make up

# Run benchmarks and submit (installs dependencies automatically)
./benchcom.sh --api-url http://localhost:8000

# Or from a remote machine
curl -sL https://raw.githubusercontent.com/mkoskinen/benchcom/main/benchcom.sh | \
  bash -s -- --api-url http://YOUR_SERVER:8000
```

- **Frontend**: http://localhost:3000
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Benchmarks

Default mode runs PassMark + OpenSSL. Use `--full` for the complete suite:

| Benchmark | Measures | Unit |
|-----------|----------|------|
| PassMark | CPU, Memory (comprehensive) | points |
| OpenSSL | SHA256, AES-256-CBC crypto | KB/s |
| sysbench | CPU (single/multi), Memory | events/sec, MiB/s |
| 7-Zip | Compression performance | MIPS |
| Pi (bc) | 5000 digit calculation | seconds |
| Disk I/O | Sequential read/write | MB/s |

```bash
./benchcom.sh --fast    # Quick mode: OpenSSL only
./benchcom.sh           # Default: PassMark + OpenSSL
./benchcom.sh --full    # Full suite: all benchmarks
```

## Platform Support

| Platform | Architectures |
|----------|---------------|
| Linux | x86_64, aarch64, armv7l, riscv64 |
| macOS | x86_64, arm64 (Apple Silicon) |

The client auto-detects platform and uses appropriate tools:
- Linux: `/proc/cpuinfo`, `free`, `/sys/class/dmi`
- macOS: `sysctl`, `system_profiler`

## Structure

```
benchcom/
├── api/          # FastAPI backend (PostgreSQL, asyncpg)
├── frontend/     # React + TypeScript frontend
├── client/       # Python benchmark client
├── benchcom.sh   # Bootstrap installer
└── Makefile      # Development commands
```

## Development

```bash
make up           # Start all services
make down         # Stop services
make logs         # View logs
make test         # Run API tests
make db-shell     # PostgreSQL shell
make db-dump      # Dump database (zstd compressed)
make clean        # Remove containers + volumes
```

### Environment Variables

Create `.env` file for production:

```bash
SECRET_KEY=your-secure-random-key
POSTGRES_PASSWORD=secure-password
AUTH_MODE=authenticated  # anonymous, authenticated, or both
```

## Client Options

```bash
./benchcom.sh [OPTIONS]

  --api-url URL       Server URL for result submission
  --api-token TOKEN   Authentication token (if AUTH_MODE=authenticated)
  --fast              Quick mode (OpenSSL only)
  --full              Full benchmark suite
  --no-install-deps   Skip dependency installation
  --output-dir DIR    Custom output directory
```

## License

MIT
