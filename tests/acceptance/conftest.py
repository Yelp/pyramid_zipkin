from unittest import mock

import pytest

from pyramid_zipkin.version import __version__


@pytest.fixture
def settings():
    return {
        'zipkin.tracing_percent': 100,
    }


@pytest.fixture
def get_span():
    return {
        'id': '17133d482ba4f605',
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
        'traceId': '66ec982fcfba8bf3b32d71d76e4a16a3',
        'localEndpoint': {
            'ipv4': mock.ANY,
            'port': 80,
            'serviceName': 'acceptance_service',
        },
        'kind': 'SERVER',
        'timestamp': mock.ANY,
        'duration': mock.ANY,
    }


@pytest.fixture
def mock_generate_random_128bit_string():
    with mock.patch(
        'pyramid_zipkin.request_helper.generate_random_128bit_string',
        return_value='66ec982fcfba8bf3b32d71d76e4a16a3',
    ) as m:
        yield m


@pytest.fixture
def mock_generate_random_64bit_string():
    with mock.patch(
        'pyramid_zipkin.request_helper.generate_random_64bit_string',
        return_value='17133d482ba4f605',
    ) as m:
        yield m
