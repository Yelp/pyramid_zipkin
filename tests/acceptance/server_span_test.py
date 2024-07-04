import json
import time
from unittest import mock

import pytest
from py_zipkin.exception import ZipkinError
from py_zipkin.zipkin import ZipkinAttrs
from webtest import TestApp as WebTestApp

from .app import main
from pyramid_zipkin.version import __version__
from tests.acceptance.test_helper import generate_app_main


@pytest.mark.parametrize(['set_post_handler_hook', 'called'], [
    (False, 0),
    (True, 1),
])
def test_sample_server_span_with_100_percent_tracing(
    default_trace_id_generator,
    get_span,
    set_post_handler_hook,
    called,
):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }

    mock_post_handler_hook = mock.Mock()
    if set_post_handler_hook:
        settings['zipkin.post_handler_hook'] = mock_post_handler_hook

    app_main, transport, _ = generate_app_main(settings)

    old_time = time.time() * 1000000

    with mock.patch(
        'pyramid_zipkin.request_helper.generate_random_64bit_string'
    ) as mock_generate_random_64bit_string:
        mock_generate_random_64bit_string.return_value = '1'
        WebTestApp(app_main).get('/sample', status=200)

    assert mock_post_handler_hook.call_count == called
    assert len(transport.output) == 1
    spans = json.loads(transport.output[0])
    assert len(spans) == 1

    span = spans[0]
    assert span['id'] == '1'
    assert span['kind'] == 'SERVER'
    assert span['timestamp'] > old_time
    assert span['duration'] > 0
    assert 'shared' not in span

    assert span == get_span


def test_upstream_zipkin_headers_sampled(default_trace_id_generator):
    settings = {'zipkin.trace_id_generator': default_trace_id_generator}
    app_main, transport, _ = generate_app_main(settings)

    trace_hex = 'aaaaaaaaaaaaaaaa'
    span_hex = 'bbbbbbbbbbbbbbbb'
    parent_hex = 'cccccccccccccccc'

    WebTestApp(app_main).get(
        '/sample',
        status=200,
        headers={
            'X-B3-TraceId': trace_hex,
            'X-B3-SpanId': span_hex,
            'X-B3-ParentSpanId': parent_hex,
            'X-B3-Flags': '0',
            'X-B3-Sampled': '1',
        },
    )

    spans = json.loads(transport.output[0])
    assert len(spans) == 1

    span = spans[0]
    assert span['traceId'] == trace_hex
    assert span['id'] == span_hex
    assert span['parentId'] == parent_hex
    assert span['kind'] == 'SERVER'
    assert span['shared'] is True


@pytest.mark.parametrize(['set_post_handler_hook', 'called'], [
    (False, 0),
    (True, 1),
])
def test_unsampled_request_has_no_span(
    default_trace_id_generator,
    set_post_handler_hook,
    called,
):
    settings = {
        'zipkin.tracing_percent': 0,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }

    mock_post_handler_hook = mock.Mock()
    if set_post_handler_hook:
        settings['zipkin.post_handler_hook'] = mock_post_handler_hook

    app_main, transport, _ = generate_app_main(settings)

    WebTestApp(app_main).get('/sample', status=200)

    assert len(transport.output) == 0
    assert mock_post_handler_hook.call_count == called


def test_blacklisted_route_has_no_span(default_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
        'zipkin.blacklisted_routes': ['sample_route'],
    }
    app_main, transport, firehose = generate_app_main(settings, firehose=True)

    WebTestApp(app_main).get('/sample', status=200)

    assert len(transport.output) == 0
    assert len(firehose.output) == 0


def test_blacklisted_path_has_no_span(default_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
        'zipkin.blacklisted_paths': [r'^/sample'],
    }
    app_main, transport, firehose = generate_app_main(settings, firehose=True)

    WebTestApp(app_main).get('/sample', status=200)

    assert len(transport.output) == 0
    assert len(firehose.output) == 0


def test_no_transport_handler_throws_error():
    app_main = main({})
    del app_main.registry.settings['zipkin.transport_handler']
    assert 'zipkin.transport_handler' not in app_main.registry.settings

    with pytest.raises(ZipkinError):
        WebTestApp(app_main).get('/sample', status=200)


def test_binary_annotations(default_trace_id_generator):
    def set_extra_binary_annotations(dummy_request, response):
        return {'other': dummy_request.registry.settings['other_attr']}

    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
        'zipkin.set_extra_binary_annotations': set_extra_binary_annotations,
        'other_attr': '42',
    }
    app_main, transport, _ = generate_app_main(settings)

    WebTestApp(app_main).get('/pet/123?test=1', status=200)

    assert len(transport.output) == 1
    spans = json.loads(transport.output[0])
    assert len(spans) == 1

    span = spans[0]
    assert span['tags'] == {
        'http.uri': '/pet/123',
        'http.uri.qs': '/pet/123?test=1',
        'http.route': '/pet/{petId}',
        'response_status_code': '200',
        'http.response.status_code': '200',
        'http.request.method': 'GET',
        'otel.status_code': 'Ok',
        'network.protocol.version': 'HTTP/1.0',
        'server.address': 'localhost',
        'server.port': '80',
        'url.path': '/pet/123',
        'url.scheme': 'http',
        'url.query': 'test=1',
        'other': '42',
        'otel.library.version': __version__,
        'otel.library.name': mock.ANY,
    }


def test_binary_annotations_404(default_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }
    app_main, transport, _ = generate_app_main(settings)

    WebTestApp(app_main).get('/abcd?test=1', status=404)

    assert len(transport.output) == 1
    spans = json.loads(transport.output[0])
    assert len(spans) == 1

    span = spans[0]
    assert span['tags'] == {
        'http.uri': '/abcd',
        'http.uri.qs': '/abcd?test=1',
        'response_status_code': '404',
        'http.request.method': 'GET',
        'http.response.status_code': '404',
        'otel.status_code': 'Unset',
        'network.protocol.version': 'HTTP/1.0',
        'server.address': 'localhost',
        'server.port': '80',
        'url.path': '/abcd',
        'url.query': 'test=1',
        'url.scheme': 'http',
        'otel.library.version': __version__,
        'otel.library.name': 'pyramid_zipkin',
    }


def test_information_route(default_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }
    app_main, transport, _ = generate_app_main(settings)

    WebTestApp(app_main).get('/information_route', status=199)

    assert len(transport.output) == 1
    spans = json.loads(transport.output[0])
    assert len(spans) == 1

    span = spans[0]
    assert span['tags'] == {
        'http.uri': '/information_route',
        'http.uri.qs': '/information_route',
        'http.route': '/information_route',
        'response_status_code': '199',
        'http.request.method': 'GET',
        'http.response.status_code': '199',
        'otel.status_code': 'Unset',
        'network.protocol.version': 'HTTP/1.0',
        'server.address': 'localhost',
        'server.port': '80',
        'url.path': '/information_route',
        'url.scheme': 'http',
        'otel.library.version': __version__,
        'otel.library.name': 'pyramid_zipkin',
    }


def test_redirect(default_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }
    app_main, transport, _ = generate_app_main(settings)

    WebTestApp(app_main).get('/redirect', status=302)

    assert len(transport.output) == 1
    spans = json.loads(transport.output[0])
    assert len(spans) == 1

    span = spans[0]
    assert span['tags'] == {
        'http.uri': '/redirect',
        'http.uri.qs': '/redirect',
        'http.route': '/redirect',
        'response_status_code': '302',
        'http.request.method': 'GET',
        'http.response.status_code': '302',
        'otel.status_code': 'Unset',
        'network.protocol.version': 'HTTP/1.0',
        'server.address': 'localhost',
        'server.port': '80',
        'url.path': '/redirect',
        'url.scheme': 'http',
        'otel.library.version': __version__,
        'otel.library.name': 'pyramid_zipkin',
    }


def test_binary_annotations_500(default_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }
    app_main, transport, _ = generate_app_main(settings)

    WebTestApp(app_main).get('/server_error', status=500)

    assert len(transport.output) == 1
    spans = json.loads(transport.output[0])
    assert len(spans) == 1

    span = spans[0]
    assert span['tags'] == {
        'http.uri': '/server_error',
        'http.uri.qs': '/server_error',
        'http.route': '/server_error',
        'response_status_code': '500',
        'http.request.method': 'GET',
        'http.response.status_code': '500',
        'otel.status_code': 'Error',
        'network.protocol.version': 'HTTP/1.0',
        'server.address': 'localhost',
        'server.port': '80',
        'url.path': '/server_error',
        'url.scheme': 'http',
        'otel.library.version': __version__,
        'otel.library.name': 'pyramid_zipkin',
    }


def test_custom_create_zipkin_attr():
    custom_create_zipkin_attr = mock.Mock(return_value=ZipkinAttrs(
        trace_id='1234',
        span_id='1234',
        parent_span_id='5678',
        flags=0,
        is_sampled=True,
    ))

    settings = {
        'zipkin.create_zipkin_attr': custom_create_zipkin_attr
    }
    app_main, transport, _ = generate_app_main(settings)

    WebTestApp(app_main).get('/sample?test=1', status=200)

    assert custom_create_zipkin_attr.called


def test_report_root_timestamp():
    settings = {
        'zipkin.report_root_timestamp': True,
        'zipkin.tracing_percent': 100.0,
    }
    app_main, transport, _ = generate_app_main(settings)

    old_time = time.time() * 1000000

    WebTestApp(app_main).get('/sample', status=200)

    assert len(transport.output) == 1
    spans = json.loads(transport.output[0])
    assert len(spans) == 1

    span = spans[0]
    # report_root_timestamp means there's no client span with the
    # same id, so the 'shared' flag should not be set.
    assert 'shared' not in span
    assert span['timestamp'] > old_time
    assert span['duration'] > 0


def test_host_and_port_in_span():
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.host': '1.2.2.1',
        'zipkin.port': 1231,
    }
    app_main, transport, _ = generate_app_main(settings)

    WebTestApp(app_main).get('/sample?test=1', status=200)

    assert len(transport.output) == 1
    spans = json.loads(transport.output[0])
    assert len(spans) == 1

    span = spans[0]
    assert span['localEndpoint'] == {
        'ipv4': '1.2.2.1',
        'port': 1231,
        'serviceName': 'acceptance_service',
    }


def test_sample_server_span_with_firehose_tracing(
        default_trace_id_generator, get_span):
    settings = {
        'zipkin.tracing_percent': 0,
        'zipkin.trace_id_generator': default_trace_id_generator,
        'zipkin.firehose_handler': default_trace_id_generator,
    }
    app_main, normal_transport, firehose_transport = generate_app_main(
        settings,
        firehose=True,
    )

    old_time = time.time() * 1000000

    with mock.patch(
        'pyramid_zipkin.request_helper.generate_random_64bit_string'
    ) as mock_generate_random_64bit_string:
        mock_generate_random_64bit_string.return_value = '1'
        WebTestApp(app_main).get('/sample', status=200)

    assert len(normal_transport.output) == 0
    assert len(firehose_transport.output) == 1
    spans = json.loads(firehose_transport.output[0])
    assert len(spans) == 1

    span = spans[0]
    assert span['timestamp'] > old_time
    assert span['duration'] > 0
    assert span == get_span


def test_max_span_batch_size(default_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 0,
        'zipkin.trace_id_generator': default_trace_id_generator,
        'zipkin.max_span_batch_size': 1,
    }
    app_main, normal_transport, firehose_transport = generate_app_main(
        settings,
        firehose=True,
    )

    WebTestApp(app_main).get('/decorator_context', status=200)

    # Assert the expected number of batches for two spans
    assert len(normal_transport.output) == 0
    assert len(firehose_transport.output) == 2

    # Assert proper hierarchy
    batch_one = json.loads(firehose_transport.output[0])
    assert len(batch_one) == 1
    child_span = batch_one[0]

    batch_two = json.loads(firehose_transport.output[1])
    assert len(batch_two) == 1
    server_span = batch_two[0]

    assert child_span['parentId'] == server_span['id']
    assert child_span['name'] == 'my_span'


def test_use_pattern_as_span_name(default_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
        'other_attr': '42',
        'zipkin.use_pattern_as_span_name': True,
    }
    app_main, transport, _ = generate_app_main(settings)

    WebTestApp(app_main).get('/pet/123?test=1', status=200)

    assert len(transport.output) == 1
    spans = json.loads(transport.output[0])

    assert len(spans) == 1
    span = spans[0]
    # Check that the span name is the pyramid pattern and not the raw url
    assert span['name'] == 'GET /pet/{petId}'


def test_defaults_at_using_raw_url_path(default_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
        'other_attr': '42',
    }
    app_main, transport, _ = generate_app_main(settings)

    WebTestApp(app_main).get('/pet/123?test=1', status=200)

    assert len(transport.output) == 1
    spans = json.loads(transport.output[0])

    assert len(spans) == 1
    span = spans[0]
    # Check that the span name is the raw url by default
    assert span['name'] == 'GET /pet/123'


def test_sample_server_ipv6(
    default_trace_id_generator,
    get_span,
):
    # Assert that pyramid_zipkin and py_zipkin correctly handle ipv6 addresses.
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }
    app_main, transport, _ = generate_app_main(settings)

    # py_zipkin uses `socket.gethostbyname` to get the current host ip if it's not
    # set in settings.
    with mock.patch(
        'socket.gethostbyname',
        return_value='2001:db8:85a3::8a2e:370:7334',
        autospec=True,
    ):
        WebTestApp(app_main).get('/sample', status=200)

    assert len(transport.output) == 1
    spans = json.loads(transport.output[0])

    assert len(spans) == 1
    span = spans[0]
    # Check that the span name is the raw url by default
    assert span['localEndpoint'] == {
        'serviceName': 'acceptance_service',
        'port': 80,
        'ipv6': '2001:db8:85a3::8a2e:370:7334',
    }
