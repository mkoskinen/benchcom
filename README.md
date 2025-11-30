# BENCHCOM

System benchmark collection and comparison tool.

## Quick Start

```bash
# Start services
make up

# Install benchmark tools and run (first time)
./benchcom.sh --install-deps --api-url http://localhost:8000

# Run benchmark and submit
./benchcom.sh --api-url http://localhost:8000

# Fast mode for quick testing
./benchcom.sh --fast --api-url http://localhost:8000
```

- **Frontend**: http://localhost:3000
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Benchmarks

- **PassMark** - CPU, Memory, Disk, System scores
- **sysbench** - CPU (single/multi-thread), Memory throughput
- **7-Zip** - Compression (MIPS)
- **OpenSSL** - SHA256, AES-256-CBC (KB/s)
- **Pi Calculation** - 5000 digits (seconds)
- **Disk I/O** - Sequential read/write (MB/s)

## Structure

```
benchcom/
├── api/          # FastAPI backend
├── frontend/     # React frontend
├── client/       # Python benchmark client
├── benchcom.sh   # Bootstrap script
└── Makefile      # Build commands
```

## Commands

```bash
make up         # Start all services
make down       # Stop services
make logs       # View logs
make clean      # Remove containers + volumes
make db-shell   # PostgreSQL shell
make lint       # Run linters
make format     # Format code
```

## Remote Usage

```bash
# On remote machine (needs Python 3.7+)
curl -sL http://YOUR_SERVER/benchcom.sh | bash -s -- --install-deps --api-url http://YOUR_SERVER:8000
```

## License

MIT
