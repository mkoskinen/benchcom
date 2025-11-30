# BENCHCOM - About & Help

## What is BENCHCOM?

BENCHCOM is a cross-platform benchmark collection and comparison tool. It allows you to run standardized benchmarks on any machine and submit results to a central server for comparison with other systems.

## Privacy & Security Considerations

### Information Collected

When you run BENCHCOM and submit results, the following information is collected:

- **System Information**: Hostname, CPU model, core count, memory size, architecture
- **Hardware Details**: Manufacturer, product name, board information (from DMI/SMBIOS)
- **OS Information**: Operating system, kernel version
- **Benchmark Results**: Performance scores and raw benchmark output
- **Network Information**: Your IP address is logged with submissions

### Security Recommendations

**For Public Servers:**

1. **Enable Authentication**: Set `AUTH_MODE=authenticated` in your `.env` file to require users to register and login before submitting benchmarks.

2. **Use Strong Secrets**: Always set a strong `SECRET_KEY` for JWT token signing in production:
   ```bash
   SECRET_KEY=$(openssl rand -base64 32)
   ```

3. **Use HTTPS**: Deploy behind a reverse proxy with TLS/SSL certificates.

4. **Review Submissions**: Benchmark console output may contain sensitive system information.

**For Users Running the Client:**

1. **Review What's Sent**: The client collects hardware and system information that could identify your machine.

2. **Hostname Privacy**: Your system's hostname is included in submissions. Consider if this reveals identifying information.

3. **Network Exposure**: Your IP address is logged when submitting results.

4. **Use Authentication**: If the server supports it, use `--api-username` and `--api-password` to associate submissions with your account.

## Running the Client

### Basic Usage

```bash
# Run with default settings (PassMark + OpenSSL)
./benchcom.sh --api-url http://server:8000

# Quick mode (OpenSSL only)
./benchcom.sh --api-url http://server:8000 --fast

# Full benchmark suite
./benchcom.sh --api-url http://server:8000 --full
```

### Authentication

```bash
# With username/password
./benchcom.sh --api-url http://server:8000 --api-username myuser --api-password mypass

# With API token
./benchcom.sh --api-url http://server:8000 --api-token YOUR_JWT_TOKEN
```

### Other Options

```bash
# Skip dependency installation
./benchcom.sh --api-url http://server:8000 --no-install-deps

# Custom output directory
./benchcom.sh --api-url http://server:8000 --output-dir ./my-results
```

## Server Administration

### Authentication Modes

Set `AUTH_MODE` in your `.env` file:

- `anonymous` - Anyone can submit benchmarks without authentication
- `authenticated` - Users must register and login to submit
- `both` (default) - Accepts both anonymous and authenticated submissions

### Admin Users

Admin users can see additional information:
- Submitter IP addresses
- Full console output logs
- User information for submissions

To make a user an admin, update their record in the database:
```sql
UPDATE users SET is_admin = true WHERE username = 'admin_username';
```

## Support

- **Issues**: https://github.com/mkoskinen/benchcom/issues
- **Source**: https://github.com/mkoskinen/benchcom

## License

MIT License - See [LICENSE](../LICENSE) for details.
