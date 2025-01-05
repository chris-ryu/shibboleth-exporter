# Shibboleth IdP Metrics Exporter

A Prometheus exporter for Shibboleth IdP metrics that converts JSON metrics from Shibboleth IdP's admin/metrics endpoint into Prometheus format.

## Features

- Collects memory statistics
- Monitors system information
- Tracks version information for Shibboleth IdP and OpenSAML
- Monitors metadata refresh timestamps
- Tracks authentication statistics
- Handles SSL verification for secure endpoints

## Metrics Exported

- **Memory Metrics**
  - shibboleth_memory_free_bytes
  - shibboleth_memory_max_bytes
  - shibboleth_memory_used_bytes
  - shibboleth_memory_usage_ratio

- **System Metrics**
  - shibboleth_cores_available

- **Version Information**
  - shibboleth_version_info (with version and opensaml_version labels)

- **Metadata Information**
  - shibboleth_metadata_refresh_timestamp (with federation labels)

- **Authentication Statistics**
  - shibboleth_authentication_password_successes

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
