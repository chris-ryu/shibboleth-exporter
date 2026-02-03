# Shibboleth IdP Metrics Exporter

A Prometheus exporter for Shibboleth IdP metrics that converts JSON metrics from Shibboleth IdP's admin/metrics endpoint into Prometheus format.

## Features

- Collects comprehensive memory statistics
- Monitors system information (CPU cores, OS, Java version)
- Tracks IdP lifecycle (startup time, uptime)
- Monitors service reload status for 10 core services
- Tracks federation metadata (refresh, expiration, errors)
- Dynamically collects authentication metrics (all methods, successes/failures)
- Handles SSL verification for secure endpoints

## Metrics Exported

### Memory Metrics (gauge)
- `shibboleth_memory_free_bytes` - Free memory in bytes
- `shibboleth_memory_max_bytes` - Maximum memory limit
- `shibboleth_memory_used_bytes` - Currently used memory
- `shibboleth_memory_usage_ratio` - Memory usage ratio (0-1)

### System Information (gauge)
- `shibboleth_cores_available` - Number of available CPU cores
- `shibboleth_info` - Info metric with labels:
  - `version` - IdP version
  - `opensaml_version` - OpenSAML version
  - `os_name`, `os_version`, `os_arch` - Operating system details
  - `java_version`, `java_vendor` - Java runtime information

### IdP Lifecycle (gauge)
- `shibboleth_idp_start_timestamp` - IdP startup time (Unix epoch)
- `shibboleth_idp_uptime_seconds` - Total uptime in seconds

### Service Reload Status (gauge, per service)
Services monitored: LoggingService, AttributeFilterService, AttributeResolverService, AttributeRegistryService, NameIdentifierGenerationService, RelyingPartyResolverService, MetadataResolverService, AccessControlService, CASServiceRegistry, ManagedBeanService

- `shibboleth_service_last_reload_attempt_timestamp` - Last reload attempt time
- `shibboleth_service_last_successful_reload_timestamp` - Last successful reload time
- `shibboleth_service_reload_success` - Boolean (1=success, 0=failure)

### Metadata Information (gauge, per federation)
- `shibboleth_metadata_last_refresh_timestamp` - Last refresh attempt
- `shibboleth_metadata_last_successful_refresh_timestamp` - Last successful refresh
- `shibboleth_metadata_last_update_timestamp` - Last actual update
- `shibboleth_metadata_valid_until_timestamp` - Metadata expiration time
- `shibboleth_metadata_has_error` - Error flag (1=has error, 0=no error)

### Authentication Statistics (counter)
- `shibboleth_authentication_total` - Authentication events with labels:
  - `method` - Authentication method (e.g., "ValidateUsernamePasswordAgainstRest")
  - `result` - "successes" or "failures"

## Requirements

- Python 3.9+
- prometheus-client
- requests
- urllib3

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/shibboleth-exporter.git
cd shibboleth-exporter
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Running with Python

```bash
python shibboleth_exporter.py
```

### Running with Docker

1. Build the Docker image:
```bash
docker build -t shibboleth-exporter .
```

2. Run the container:
```bash
docker run -p 9090:9090 \
  -e PORT=9090 \
  -e METRICS_ENDPOINT=https://your-shibboleth-host/idp/profile/admin/metrics \
  shibboleth-exporter
```

### Using Docker Compose

1. Create a docker-compose.yml file:
```yaml
version: '3'
services:
  shibboleth-exporter:
    build: .
    ports:
      - "9090:9090"
    environment:
      - PORT=9090
      - METRICS_ENDPOINT=https://your-shibboleth-host/idp/profile/admin/metrics
    restart: unless-stopped
```

2. Run with docker-compose:
```bash
docker-compose up -d
```

## Configuration

The exporter can be configured using environment variables:

- `PORT`: The port on which the exporter will listen (default: 9090)
- `METRICS_ENDPOINT`: The Shibboleth IdP metrics endpoint URL (default: https://localhost/idp/profile/admin/metrics)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Shibboleth IdP team for providing the metrics endpoint
- Prometheus team for the client libraries

## Support

If you encounter any issues or have questions, please file an issue on the GitHub repository.
