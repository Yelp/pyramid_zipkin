from unittest import mock

import pytest

from pyramid_zipkin.version import __version__


@pytest.fixture
def default_trace_id_generator(dummy_request):
    return lambda dummy_request: '17133d482ba4f605'


@pytest.fixture
def settings():
    return {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }


@pytest.fixture
def get_span():
    return {
        'id': '1',
        'tags': {
            'http.uri': '/sample',
            'http.uri.qs': '/sample',
            'http.route': '/sample',
            'url.path': '/sample',
            'url.scheme': 'http',
            'network.protocol.version': 'HTTP/1.0',
            'server.address': 'localhost',
            'server.port': '80',
            'response_status_code': '200',
            'http.response.status_code': '200',
            'http.request.method': 'GET',
            'otel.status_code': 'Ok',
            'otel.library.version': __version__,
            'otel.library.name': 'pyramid_zipkin',
        },
        'name': 'GET /sample',
        'traceId': '17133d482ba4f605',
        'localEndpoint': {
            'ipv4': mock.ANY,
            'port': 80,
            'serviceName': 'acceptance_service',
        },
        'kind': 'SERVER',
        'timestamp': mock.ANY,
        'duration': mock.ANY,
    }
