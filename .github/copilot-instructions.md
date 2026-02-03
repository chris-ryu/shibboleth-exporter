# Copilot Instructions for Shibboleth IdP Metrics Exporter

## Project Overview

Single-file Prometheus exporter that polls Shibboleth IdP's `/idp/profile/admin/metrics` JSON endpoint and exposes metrics in Prometheus format on port 9090. This is a bridge service, not a full IdP implementation.

## Architecture

**Data Flow**: Shibboleth IdP JSON metrics → [shibboleth_exporter.py](../shibboleth_exporter.py) → Prometheus scrape endpoint

- **Single collector class**: `ShibbolethCollector` fetches JSON from IdP endpoint on every Prometheus scrape
- **No persistence**: Stateless service, metrics computed on-demand from live IdP data
- **Polling pattern**: Main loop runs `time.sleep(1)` to keep HTTP server alive; actual collection happens on scrape
- **SSL disabled**: `urllib3.disable_warnings()` and `verify=False` for self-signed certs (common in internal IdP deployments)

## Key Components

### [shibboleth_exporter.py](../shibboleth_exporter.py)
- **Lines 16-18**: `ShibbolethCollector` initialized with IdP metrics endpoint URL
- **Lines 20-43**: Helper methods for timestamp and duration parsing (ISO 8601 format)
- **Lines 45-58**: `collect()` method orchestrates 6 metric collection functions
- **Lines 60-227**: Modular metric collection functions:
  - `_collect_memory_metrics()`: Memory usage (free/max/used bytes, usage ratio)
  - `_collect_system_info()`: CPU cores, OS/Java version info as labels
  - `_collect_idp_lifecycle()`: IdP startup time, uptime in seconds
  - `_collect_service_reload_metrics()`: 10 services reload timestamps and success flags
  - `_collect_metadata_metrics()`: Federation metadata refresh/update/expiration timestamps, error flags
  - `_collect_authentication_metrics()`: All authentication methods with dynamic pattern matching (successes/failures)
- **Lines 229-236**: Configuration via env vars `PORT` and `METRICS_ENDPOINT`

### Metric Patterns
- **Gauge metrics**: Use `Metric(..., 'gauge')` for instant values (memory, cores)
- **Counter metrics**: Use `Metric(..., 'counter')` for cumulative counts (auth successes)
- **Label-based metrics**: Version and federation info stored as labels, not separate metrics
- **Timestamp conversion**: Metadata refresh times converted from ISO8601 to Unix epoch via `datetime.strptime().timestamp()`

## Development Workflow

### Local Testing
```bash
# Install dependencies
pip install -r requirements.txt

# Run exporter (requires accessible Shibboleth IdP)
METRICS_ENDPOINT=https://your-idp/idp/profile/admin/metrics python shibboleth_exporter.py

# Test metrics endpoint
curl http://localhost:9090/metrics
```

### Docker Workflow
```bash
# Build image
docker build -t shibboleth-exporter .

# Run with custom endpoint
docker run -p 9090:9090 -e METRICS_ENDPOINT=https://idp.example.com/idp/profile/admin/metrics shibboleth-exporter

# Production deployment
docker-compose up -d
```

## Project Conventions

- **No external config files**: All configuration via environment variables
- **Hardcoded metric names**: Metric names match Shibboleth JSON keys with `shibboleth_` prefix (e.g., `memory.free.bytes` → `shibboleth_memory_free_bytes`)
- **Error handling**: Currently minimal - service fails hard if IdP endpoint unreachable (no retry logic)
- **JSON structure dependency**: Code assumes specific Shibboleth metrics JSON schema (gauges/counters structure)

## Adding New Metrics

When adding metrics from Shibboleth JSON response:
1. Identify if it's in `gauges` or `counters` section
2. Choose correct metric type (`gauge` for instant values, `counter` for cumulative)
3. Use `add_sample()` with descriptive name following `shibboleth_*` naming
4. Extract nested values carefully (see metadata_refresh dict iteration pattern at lines 53-57)
5. Add labels for dimensional data (federation, auth method, etc.)

## Integration Points

- **Shibboleth IdP**: Expects JSON from `/idp/profile/admin/metrics` endpoint (configured in IdP's metrics configuration)
- **Prometheus**: Service must be added to Prometheus `scrape_configs` with appropriate `scrape_interval` (recommend 30s-60s)
- **Docker networking**: In docker-compose, use service name or bridge network to reach IdP

## Additional Metric Sources

### IdP Admin Metrics Endpoint (`/idp/profile/admin/metrics`)
Primary data source providing comprehensive JSON metrics. **Fully implemented** in current exporter.

#### Available and Collected Metrics

**Memory Metrics** (gauge):
- `shibboleth_memory_free_bytes`: Free memory in bytes
- `shibboleth_memory_max_bytes`: Maximum memory limit
- `shibboleth_memory_used_bytes`: Currently used memory
- `shibboleth_memory_usage_ratio`: Memory usage ratio (0-1)

**System Information** (gauge):
- `shibboleth_cores_available`: Number of available CPU cores
- `shibboleth_info`: Info metric with labels:
  - `version`: IdP version (e.g., "4.2.1")
  - `opensaml_version`: OpenSAML version (e.g., "4.2.0")
  - `os_name`, `os_version`, `os_arch`: Operating system details
  - `java_version`, `java_vendor`: Java runtime information

**IdP Lifecycle Metrics** (gauge):
- `shibboleth_idp_start_timestamp`: IdP startup time (Unix epoch)
- `shibboleth_idp_uptime_seconds`: Total uptime in seconds (parsed from PT duration)

**Service Reload Metrics** (gauge, per service):
Services monitored: LoggingService, AttributeFilterService, AttributeResolverService, AttributeRegistryService, NameIdentifierGenerationService, RelyingPartyResolverService, MetadataResolverService, AccessControlService, CASServiceRegistry, ManagedBeanService

- `shibboleth_service_last_reload_attempt_timestamp`: Last reload attempt time
- `shibboleth_service_last_successful_reload_timestamp`: Last successful reload time
- `shibboleth_service_reload_success`: Boolean (1=success, 0=failure)

**Metadata Metrics** (gauge, per federation):
- `shibboleth_metadata_last_refresh_timestamp`: Last refresh attempt
- `shibboleth_metadata_last_successful_refresh_timestamp`: Last successful refresh
- `shibboleth_metadata_last_update_timestamp`: Last actual update
- `shibboleth_metadata_valid_until_timestamp`: Metadata expiration time
- `shibboleth_metadata_has_error`: Error flag (1=has error, 0=no error)

**Authentication Metrics** (counter, dynamically collected):
- `shibboleth_authentication_total`: Authentication events with labels:
  - `method`: Authentication method (e.g., "ValidateUsernamePasswordAgainstRest")
  - `result`: "successes" or "failures"

#### Implementation Notes

**Timestamp Parsing**:
- ISO 8601 format: `2026-02-03T02:32:58.125178Z` → Unix epoch via `datetime.strptime()`
- Duration format: `PT3808H26M55.392S` → seconds via regex pattern matching

**Dynamic Collection**:
- Authentication metrics use pattern matching on `net.shibboleth.idp.authn.*`
- Service reload metrics iterate through predefined service mapping
- Metadata metrics iterate through federation names from JSON response

**Error Handling**:
- Graceful degradation with `.get()` for optional fields
- Separate try/except for `rootValidUntil` timestamp format (no microseconds)

**Sample JSON Structure**:
```json
{
  "gauges": {
    "memory.free.bytes": {"value": 327089776},
    "net.shibboleth.idp.starttime": {"value": "2025-08-28T11:32:13.054Z"},
    "net.shibboleth.idp.uptime": {"value": "PT3808H26M55.392S"},
    "net.shibboleth.idp.logging.reload.attempt": {"value": "2025-08-28T11:32:15.068Z"},
    "net.shibboleth.idp.metadata.rootValidUntil": {"value": {"jst-univ-federation": "2026-02-10T02:32:58Z"}}
  },
  "counters": {
    "net.shibboleth.idp.authn.ValidateUsernamePasswordAgainstRest.successes": {"count": 2627},
    "net.shibboleth.idp.authn.ValidateUsernamePasswordAgainstRest.failures": {"count": 189}
  }
}
```

### IdP Status Page (`/idp/status`) - NOT IMPLEMENTED

Alternative text-based data source. **Not currently implemented** as JSON endpoint provides all necessary information.

#### Why /idp/status Parsing Was Skipped

1. **Redundant Information**: All metrics from status page are already available in JSON endpoint
2. **Parsing Complexity**: Text parsing is more fragile than JSON parsing
3. **Maintenance Burden**: HTML/text structure changes would break parser
4. **No Unique Value**: Only unique data (enabled modules list, installed plugins) deemed non-critical

**If Future Implementation Needed**:
- Add environment variable `ENABLE_STATUS_PARSING=true`
- Parse structured text sections with regex
- Extract enabled modules and installed plugins lists
- Cross-reference with JSON data for validation

**Sample URL**: `https://kijeon.jst.ac.kr/idp/status`
