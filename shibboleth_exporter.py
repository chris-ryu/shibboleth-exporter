from prometheus_client import start_http_server, Metric, REGISTRY
import json
import requests
import sys
import time
import urllib3
from datetime import datetime

import os



urllib3.disable_warnings()

class ShibbolethCollector(object):
    def __init__(self, endpoint):
        self._endpoint = endpoint

    def collect(self):
        # Fetch the JSON
        response = json.loads(requests.get(self._endpoint, verify=False).content.decode('UTF-8'))

        # Memory metrics
        memory_metric = Metric('shibboleth_memory', 'Memory statistics', 'gauge')
        memory_metric.add_sample('shibboleth_memory_free_bytes', 
            value=response['gauges']['memory.free.bytes']['value'], labels={})
        memory_metric.add_sample('shibboleth_memory_max_bytes', 
            value=response['gauges']['memory.max.bytes']['value'], labels={})
        memory_metric.add_sample('shibboleth_memory_used_bytes', 
            value=response['gauges']['memory.used.bytes']['value'], labels={})
        memory_metric.add_sample('shibboleth_memory_usage_ratio', 
            value=response['gauges']['memory.usage']['value'], labels={})
        yield memory_metric

        # System info metrics
        system_metric = Metric('shibboleth_system_info', 'System information', 'gauge')
        system_metric.add_sample('shibboleth_cores_available', 
            value=response['gauges']['cores.available']['value'], labels={})
        yield system_metric

        # Version info
        version_metric = Metric('shibboleth_version_info', 'Version information', 'gauge')
        version_metric.add_sample('shibboleth_version_info', value=1, labels={
            'version': response['gauges']['net.shibboleth.idp.version']['value'],
            'opensaml_version': response['gauges']['org.opensaml.version']['value']
        })
        yield version_metric

        # Metadata metrics
        metadata_metric = Metric('shibboleth_metadata', 'Metadata information', 'gauge')
        metadata_refresh = response['gauges']['net.shibboleth.idp.metadata.refresh']['value']
        for federation, timestamp in metadata_refresh.items():
            metadata_metric.add_sample('shibboleth_metadata_refresh_timestamp', 
                value=datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S.%fZ').timestamp(),
                labels={'federation': federation})
        yield metadata_metric

        # Authentication metrics
        auth_metric = Metric('shibboleth_authentication', 'Authentication statistics', 'counter')
        if 'net.shibboleth.idp.authn.ValidateUsernamePasswordAgainstRest.successes' in response['counters']:
            auth_metric.add_sample('shibboleth_authentication_password_successes',
                value=response['counters']['net.shibboleth.idp.authn.ValidateUsernamePasswordAgainstRest.successes']['count'],
                labels={})
        yield auth_metric

port = int(os.getenv('PORT', '9090'))
metrics_endpoint = os.getenv('METRICS_ENDPOINT', 'https://localhost/idp/profile/admin/metrics')

if __name__ == '__main__':
    start_http_server(port)
    REGISTRY.register(ShibbolethCollector(metrics_endpoint))

    while True:
        time.sleep(1)
