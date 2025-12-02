# BENCHCOM Client

Python benchmark runner (v1.1).

## Usage

```bash
# Run and submit to API
python3 benchcom.py --api-url http://localhost:8000

# Fast mode (pi + sysbench only)
python3 benchcom.py --fast --api-url http://localhost:8000

# Check version
python3 benchcom.py --version
```

Results saved to `benchcom_<hostname>_<timestamp>/`.

## Benchmarks

| Test | Category | Unit |
|------|----------|------|
| PassMark | cpu/memory/disk/overall | points |
| sysbench CPU | cpu | events/sec |
| sysbench Memory | memory | MiB/sec |
| 7-Zip | compression | MIPS |
| OpenSSL SHA256 | cryptography | KB/s |
| OpenSSL AES-256 | cryptography | KB/s |
| Pi Calculation | cpu | seconds |
| Disk Read/Write | disk | MB/s |

Missing tools are skipped automatically.

## Dependencies

Install via `benchcom.sh --install-deps` or manually:
- p7zip
- openssl
- sysbench
- PassMark pt_linux (optional)

## Requirements

- Python 3.7+
- `requests` library (for API submission)
