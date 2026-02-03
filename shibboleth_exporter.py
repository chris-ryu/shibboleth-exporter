from prometheus_client import Metric, CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
from flask import Flask, request, Response
import json
import requests
import re
import sys
import time
import urllib3
from datetime import datetime

import os


urllib3.disable_warnings()

app = Flask(__name__)


class ShibbolethCollector(object):
    def __init__(self, endpoint, target_label=None):
        self._endpoint = endpoint
        self._target_label = target_label or endpoint

    def _parse_iso8601_timestamp(self, timestamp_str):
        """Convert ISO 8601 timestamp to Unix epoch."""
        if timestamp_str is None:
            return None
        return datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M:%S.%fZ').timestamp()

    def _parse_iso8601_duration(self, duration_str):
        """Convert ISO 8601 duration (PT format) to seconds."""
        if not duration_str or not duration_str.startswith('PT'):
            return 0
        
        # Parse PT3808H26M55.392S format
        pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?'
        match = re.match(pattern, duration_str)
        if not match:
            return 0
        
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = float(match.group(3) or 0)
        
        return hours * 3600 + minutes * 60 + seconds

    def collect(self):
        # Fetch the JSON with error handling
        try:
            resp = requests.get(self._endpoint, verify=False, timeout=10)
            resp.raise_for_status()
            content = resp.content.decode('UTF-8', errors='ignore')
            if not content.strip():
                print(f"Warning: Empty response from {self._endpoint}")
                return
            response = json.loads(content)
        except requests.exceptions.RequestException as e:
            print(f"Error fetching metrics from {self._endpoint}: {e}")
            # Return a basic up metric showing the exporter is running but can't reach IdP
            up_metric = Metric('shibboleth_up', 'Shibboleth IdP reachability', 'gauge')
            up_metric.add_sample('shibboleth_up', value=0, labels={})
            yield up_metric
            return
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON from {self._endpoint}: {e}")
            up_metric = Metric('shibboleth_up', 'Shibboleth IdP reachability', 'gauge')
            up_metric.add_sample('shibboleth_up', value=0, labels={})
            yield up_metric
            return
        
        # IdP is reachable
        up_metric = Metric('shibboleth_up', 'Shibboleth IdP reachability', 'gauge')
        up_metric.add_sample('shibboleth_up', value=1, labels={})
        yield up_metric
        
        gauges = response.get('gauges', {})
        counters = response.get('counters', {})
        
        # Collect all metric families
        yield from self._collect_memory_metrics(gauges)
        yield from self._collect_system_info(gauges)
        yield from self._collect_idp_lifecycle(gauges)
        yield from self._collect_service_reload_metrics(gauges)
        yield from self._collect_metadata_metrics(gauges)
        yield from self._collect_authentication_metrics(counters)

    def _collect_memory_metrics(self, gauges):
        """Collect memory-related metrics."""
        memory_metric = Metric('shibboleth_memory', 'Memory statistics', 'gauge')
        memory_metric.add_sample('shibboleth_memory_free_bytes',
            value=gauges['memory.free.bytes']['value'], labels={})
        memory_metric.add_sample('shibboleth_memory_max_bytes',
            value=gauges['memory.max.bytes']['value'], labels={})
        memory_metric.add_sample('shibboleth_memory_used_bytes',
            value=gauges['memory.used.bytes']['value'], labels={})
        memory_metric.add_sample('shibboleth_memory_usage_ratio',
            value=gauges['memory.usage']['value'], labels={})
        yield memory_metric

    def _collect_system_info(self, gauges):
        """Collect system and environment information."""
        system_metric = Metric('shibboleth_system_info', 'System information', 'gauge')
        system_metric.add_sample('shibboleth_cores_available',
            value=gauges['cores.available']['value'], labels={})
        yield system_metric
        
        # OS and Java info as labels
        info_metric = Metric('shibboleth_info', 'Shibboleth IdP information', 'gauge')
        info_metric.add_sample('shibboleth_info', value=1, labels={
            'version': gauges.get('net.shibboleth.idp.version', {}).get('value', 'unknown'),
            'opensaml_version': gauges.get('org.opensaml.version', {}).get('value', 'unknown'),
            'os_name': gauges.get('os.name', {}).get('value', 'unknown'),
            'os_version': gauges.get('os.version', {}).get('value', 'unknown'),
            'os_arch': gauges.get('os.arch', {}).get('value', 'unknown'),
            'java_version': gauges.get('java.version', {}).get('value', 'unknown'),
            'java_vendor': gauges.get('java.vendor', {}).get('value', 'unknown')
        })
        yield info_metric

    def _collect_idp_lifecycle(self, gauges):
        """Collect IdP lifecycle metrics (startup time, uptime)."""
        lifecycle_metric = Metric('shibboleth_idp_lifecycle', 'IdP lifecycle information', 'gauge')
        
        # Start time
        starttime = gauges.get('net.shibboleth.idp.starttime', {}).get('value')
        if starttime:
            lifecycle_metric.add_sample('shibboleth_idp_start_timestamp',
                value=self._parse_iso8601_timestamp(starttime),
                labels={})
        
        # Uptime
        uptime = gauges.get('net.shibboleth.idp.uptime', {}).get('value')
        if uptime:
            lifecycle_metric.add_sample('shibboleth_idp_uptime_seconds',
                value=self._parse_iso8601_duration(uptime),
                labels={})
        
        yield lifecycle_metric

    def _collect_service_reload_metrics(self, gauges):
        """Collect service reload status metrics."""
        service_metric = Metric('shibboleth_service_reload', 'Service reload status', 'gauge')
        
        # Service name mapping
        services = {
            'logging': 'LoggingService',
            'attribute.filter': 'AttributeFilterService',
            'attribute.resolver': 'AttributeResolverService',
            'attribute.registry': 'AttributeRegistryService',
            'nameid': 'NameIdentifierGenerationService',
            'relyingparty': 'RelyingPartyResolverService',
            'metadata': 'MetadataResolverService',
            'accesscontrol': 'AccessControlService',
            'cas.registry': 'CASServiceRegistry',
            'managedbean': 'ManagedBeanService'
        }
        
        for service_key, service_name in services.items():
            prefix = f'net.shibboleth.idp.{service_key}.reload'
            
            attempt = gauges.get(f'{prefix}.attempt', {}).get('value')
            success = gauges.get(f'{prefix}.success', {}).get('value')
            error = gauges.get(f'{prefix}.error', {}).get('value')
            
            if attempt:
                service_metric.add_sample('shibboleth_service_last_reload_attempt_timestamp',
                    value=self._parse_iso8601_timestamp(attempt),
                    labels={'service': service_name})
            
            if success:
                service_metric.add_sample('shibboleth_service_last_successful_reload_timestamp',
                    value=self._parse_iso8601_timestamp(success),
                    labels={'service': service_name})
            
            # Reload success flag (1 if no error and success == attempt, 0 otherwise)
            if attempt and success:
                is_success = 1 if (error is None and attempt == success) else 0
                service_metric.add_sample('shibboleth_service_reload_success',
                    value=is_success,
                    labels={'service': service_name})
        
        yield service_metric

    def _collect_metadata_metrics(self, gauges):
        """Collect enhanced metadata metrics."""
        metadata_metric = Metric('shibboleth_metadata', 'Metadata information', 'gauge')
        
        # Last refresh timestamps
        metadata_refresh = gauges.get('net.shibboleth.idp.metadata.refresh', {}).get('value', {})
        for federation, timestamp in metadata_refresh.items():
            if timestamp:
                metadata_metric.add_sample('shibboleth_metadata_last_refresh_timestamp',
                    value=self._parse_iso8601_timestamp(timestamp),
                    labels={'federation': federation})
        
        # Last successful refresh
        successful_refresh = gauges.get('net.shibboleth.idp.metadata.successfulRefresh', {}).get('value', {})
        for federation, timestamp in successful_refresh.items():
            if timestamp:
                metadata_metric.add_sample('shibboleth_metadata_last_successful_refresh_timestamp',
                    value=self._parse_iso8601_timestamp(timestamp),
                    labels={'federation': federation})
        
        # Last update
        metadata_update = gauges.get('net.shibboleth.idp.metadata.update', {}).get('value', {})
        for federation, timestamp in metadata_update.items():
            if timestamp:
                metadata_metric.add_sample('shibboleth_metadata_last_update_timestamp',
                    value=self._parse_iso8601_timestamp(timestamp),
                    labels={'federation': federation})
        
        # Valid until (expiration)
        valid_until = gauges.get('net.shibboleth.idp.metadata.rootValidUntil', {}).get('value', {})
        for federation, timestamp in valid_until.items():
            if timestamp:
                # rootValidUntil uses a different format without microseconds
                try:
                    ts = datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%SZ').timestamp()
                    metadata_metric.add_sample('shibboleth_metadata_valid_until_timestamp',
                        value=ts,
                        labels={'federation': federation})
                except:
                    pass
        
        # Metadata errors
        metadata_errors = gauges.get('net.shibboleth.idp.metadata.error', {}).get('value', {})
        for federation in metadata_refresh.keys():
            has_error = 1 if federation in metadata_errors else 0
            metadata_metric.add_sample('shibboleth_metadata_has_error',
                value=has_error,
                labels={'federation': federation})
        
        yield metadata_metric

    def _collect_authentication_metrics(self, counters):
        """Collect authentication metrics dynamically."""
        auth_metric = Metric('shibboleth_authentication', 'Authentication statistics', 'counter')
        
        # Pattern: net.shibboleth.idp.authn.{Method}.{successes|failures}
        for counter_name, counter_data in counters.items():
            if counter_name.startswith('net.shibboleth.idp.authn.'):
                # Extract method and result
                parts = counter_name.replace('net.shibboleth.idp.authn.', '').rsplit('.', 1)
                if len(parts) == 2:
                    method = parts[0]
                    result = parts[1]  # 'successes' or 'failures'
                    
                    auth_metric.add_sample('shibboleth_authentication_total',
                        value=counter_data['count'],
                        labels={'method': method, 'result': result})
        
        yield auth_metric


# Flask routes for multi-target exporter pattern

@app.route('/probe')
def probe():
    """
    Multi-target probe endpoint (like blackbox_exporter).
    Usage: /probe?target=https://idp.example.com/idp/profile/admin/metrics
    """
    target = request.args.get('target')
    if not target:
        return Response(
            "Missing required 'target' parameter\n"
            "Usage: /probe?target=https://your-idp/idp/profile/admin/metrics\n",
            status=400,
            mimetype='text/plain'
        )
    
    # Create a new registry for this request
    registry = CollectorRegistry()
    collector = ShibbolethCollector(target, target_label=target)
    registry.register(collector)
    
    # Generate and return metrics
    return Response(
        generate_latest(registry),
        mimetype=CONTENT_TYPE_LATEST
    )


@app.route('/metrics')
def metrics():
    """
    Legacy single-target endpoint for backward compatibility.
    Uses METRICS_ENDPOINT environment variable.
    """
    endpoint = os.getenv('METRICS_ENDPOINT')
    if not endpoint:
        return Response(
            "METRICS_ENDPOINT environment variable not set.\n"
            "Use /probe?target=<url> for multi-target mode.\n",
            status=400,
            mimetype='text/plain'
        )
    
    registry = CollectorRegistry()
    collector = ShibbolethCollector(endpoint, target_label=endpoint)
    registry.register(collector)
    
    return Response(
        generate_latest(registry),
        mimetype=CONTENT_TYPE_LATEST
    )


@app.route('/health')
@app.route('/')
def health():
    """Health check endpoint."""
    return Response(
        "Shibboleth Exporter is running.\n"
        "Endpoints:\n"
        "  /probe?target=<url>  - Multi-target probe (recommended)\n"
        "  /metrics             - Single target (requires METRICS_ENDPOINT env var)\n"
        "  /health              - Health check\n",
        mimetype='text/plain'
    )


port = int(os.getenv('PORT', '9090'))

if __name__ == '__main__':
    print(f"Starting Shibboleth Exporter on port {port}")
    print(f"  /probe?target=<url>  - Multi-target probe endpoint")
    print(f"  /metrics             - Legacy single-target endpoint")
    app.run(host='0.0.0.0', port=port, threaded=True)
