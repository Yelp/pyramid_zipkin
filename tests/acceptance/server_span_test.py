# -*- coding: utf-8 -*-
import time

import mock
import pytest
from py_zipkin.exception import ZipkinError
from py_zipkin.util import unsigned_hex_to_signed_int
from py_zipkin.zipkin import ZipkinAttrs
from webtest import TestApp as WebTestApp

from .app import main
from tests.acceptance import test_helper
from tests.acceptance.test_helper import decode_thrift
from tests.acceptance.test_helper import generate_app_main


@pytest.mark.parametrize(['set_callback', 'called'], [(False, 0), (True, 1)])
def test_sample_server_span_with_100_percent_tracing(
    default_trace_id_generator,
    get_span,
    set_callback,
    called,
):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }

    mock_post_processor_callback = mock.Mock()
    if set_callback:
        settings['zipkin.post_processor_callback'] = mock_post_processor_callback

    app_main, transport, _ = generate_app_main(settings)

    old_time = time.time() * 1000000

    def validate_span(span_objs):
        assert len(span_objs) == 1
        span_obj = span_objs[0]
        result_span = test_helper.massage_result_span(span_obj)
        timestamps = test_helper.get_timestamps(result_span)
        get_span['trace_id'] = unsigned_hex_to_signed_int(
            default_trace_id_generator(span_obj),
        )
        # The request to this service had no incoming Zipkin headers, so it's
        # assumed to be the root span of a trace, which means it logs
        # timestamp and duration.
        assert result_span.pop('timestamp') > old_time
        assert result_span.pop('duration') > 0
        assert get_span == result_span
        assert old_time <= timestamps['sr']
        assert timestamps['sr'] <= timestamps['ss']

    with mock.patch(
        'pyramid_zipkin.request_helper.generate_random_64bit_string'
    ) as mock_generate_random_64bit_string:
        mock_generate_random_64bit_string.return_value = '1'
        WebTestApp(app_main).get('/sample', status=200)

    assert len(transport.output) == 1
    validate_span(decode_thrift(transport.output[0]))
    assert mock_post_processor_callback.call_count == called


def test_upstream_zipkin_headers_sampled(default_trace_id_generator):
    settings = {'zipkin.trace_id_generator': default_trace_id_generator}
    app_main, transport, _ = generate_app_main(settings)

    trace_hex = 'aaaaaaaaaaaaaaaa'
    span_hex = 'bbbbbbbbbbbbbbbb'
    parent_hex = 'cccccccccccccccc'

    def validate(span_objs):
        assert len(span_objs) == 1
        span = span_objs[0]
        assert span.trace_id == unsigned_hex_to_signed_int(trace_hex)
        assert span.id == unsigned_hex_to_signed_int(span_hex)
        assert span.parent_id == unsigned_hex_to_signed_int(parent_hex)
        # Since Zipkin headers are passed in, the span in assumed to be the
        # server part of a span started by an upstream client, so doesn't have
        # to log timestamp/duration.
        assert span.timestamp is None
        assert span.duration is None

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

    validate(decode_thrift(transport.output[0]))


@pytest.mark.parametrize(['set_callback', 'called'], [(False, 0), (True, 1)])
def test_unsampled_request_has_no_span(
    default_trace_id_generator,
    set_callback,
    called,
):
    settings = {
        'zipkin.tracing_percent': 0,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }

    mock_post_processor_callback = mock.Mock()
    if set_callback:
        settings['zipkin.post_processor_callback'] = mock_post_processor_callback

    app_main, transport, _ = generate_app_main(settings)

    WebTestApp(app_main).get('/sample', status=200)

    assert len(transport.output) == 0
    assert mock_post_processor_callback.call_count == called


def test_blacklisted_route_has_no_span(default_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
        'zipkin.blacklisted_routes': ['sample_route'],
    }
    app_main, transport, _ = generate_app_main(settings)

    WebTestApp(app_main).get('/sample', status=200)

    assert len(transport.output) == 0


def test_blacklisted_path_has_no_span(default_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
        'zipkin.blacklisted_paths': [r'^/sample'],
    }
    app_main, transport, _ = generate_app_main(settings)

    WebTestApp(app_main).get('/sample', status=200)

    assert len(transport.output) == 0


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

    def validate_span(span_objs):
        assert len(span_objs) == 1
        span_obj = span_objs[0]
        # Assert that the only present binary_annotations are ones we expect
        expected_annotations = {
            'http.uri': '/pet/123',
            'http.uri.qs': '/pet/123?test=1',
            'http.route': '/pet/{petId}',
            'response_status_code': '200',
            'other': '42',
        }
        result_span = test_helper.massage_result_span(span_obj)
        for ann in result_span['binary_annotations']:
            assert ann['value'] == expected_annotations.pop(ann['key'])
        assert len(expected_annotations) == 0

    WebTestApp(app_main).get('/pet/123?test=1', status=200)

    assert len(transport.output) == 1
    validate_span(decode_thrift(transport.output[0]))


def test_binary_annotations_404(default_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }
    app_main, transport, _ = generate_app_main(settings)

    def validate_span(span_objs):
        assert len(span_objs) == 1
        span_obj = span_objs[0]
        # Assert that the only present binary_annotations are ones we expect
        expected_annotations = {
            'http.uri': '/abcd',
            'http.uri.qs': '/abcd?test=1',
            'http.route': '',
            'response_status_code': '404',
        }
        result_span = test_helper.massage_result_span(span_obj)
        for ann in result_span['binary_annotations']:
            assert ann['value'] == expected_annotations.pop(ann['key'])
        assert len(expected_annotations) == 0

    WebTestApp(app_main).get('/abcd?test=1', status=404)

    assert len(transport.output) == 1
    validate_span(decode_thrift(transport.output[0]))


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

    def check_for_timestamp_and_duration(span_objs):
        span_obj = span_objs[0]
        assert span_obj.timestamp > old_time
        assert span_obj.duration > 0

    WebTestApp(app_main).get('/sample', status=200)

    assert len(transport.output) == 1
    check_for_timestamp_and_duration(decode_thrift(transport.output[0]))


def test_host_and_port_in_span():
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.host': '1.2.2.1',
        'zipkin.port': 1231,
    }
    app_main, transport, _ = generate_app_main(settings)

    def validate_span(span_objs):
        assert len(span_objs) == 1
        span_obj = span_objs[0]
        # Assert ipv4 and port match what we expect
        expected_ipv4 = (1 << 24) | (2 << 16) | (2 << 8) | 1
        assert expected_ipv4 == span_obj.annotations[0].host.ipv4
        assert 1231 == span_obj.annotations[0].host.port

    WebTestApp(app_main).get('/sample?test=1', status=200)

    assert len(transport.output) == 1
    validate_span(decode_thrift(transport.output[0]))


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

    def validate_span(span_objs):
        assert len(span_objs) == 1
        span_obj = span_objs[0]
        result_span = test_helper.massage_result_span(span_obj)
        timestamps = test_helper.get_timestamps(result_span)
        get_span['trace_id'] = unsigned_hex_to_signed_int(
            default_trace_id_generator(span_obj),
        )
        # The request to this service had no incoming Zipkin headers, so it's
        # assumed to be the root span of a trace, which means it logs
        # timestamp and duration.
        assert result_span.pop('timestamp') > old_time
        assert result_span.pop('duration') > 0
        assert get_span == result_span
        assert old_time <= timestamps['sr']
        assert timestamps['sr'] <= timestamps['ss']

    with mock.patch(
        'pyramid_zipkin.request_helper.generate_random_64bit_string'
    ) as mock_generate_random_64bit_string:
        mock_generate_random_64bit_string.return_value = '1'
        WebTestApp(app_main).get('/sample', status=200)

    assert len(normal_transport.output) == 0
    assert len(firehose_transport.output) == 1
    validate_span(decode_thrift(firehose_transport.output[0]))


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
    batch_one = decode_thrift(firehose_transport.output[0])
    assert len(batch_one) == 1
    child_span = batch_one[0]

    batch_two = decode_thrift(firehose_transport.output[1])
    assert len(batch_two) == 1
    server_span = batch_two[0]

    assert child_span.parent_id == server_span.id
    assert child_span.name == 'my_span'


def test_use_pattern_as_span_name(default_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
        'other_attr': '42',
        'zipkin.use_pattern_as_span_name': True,
    }
    app_main, transport, _ = generate_app_main(settings)

    def validate_span(span_objs):
        assert len(span_objs) == 1
        result_span = test_helper.massage_result_span(span_objs[0])
        # Check that the span name is the pyramid pattern and not the raw url
        assert result_span['name'] == 'GET /pet/{petId}'

    WebTestApp(app_main).get('/pet/123?test=1', status=200)

    assert len(transport.output) == 1
    validate_span(decode_thrift(transport.output[0]))


def test_defaults_at_using_raw_url_path(default_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
        'other_attr': '42',
    }
    app_main, transport, _ = generate_app_main(settings)

    def validate_span(span_objs):
        assert len(span_objs) == 1
        result_span = test_helper.massage_result_span(span_objs[0])
        # Check that the span name is the raw url by default
        assert result_span['name'] == 'GET /pet/123'

    WebTestApp(app_main).get('/pet/123?test=1', status=200)

    assert len(transport.output) == 1
    validate_span(decode_thrift(transport.output[0]))
