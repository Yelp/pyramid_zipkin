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


def test_sample_server_span_with_100_percent_tracing(
        thrift_obj, default_trace_id_generator, get_span):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }

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

    thrift_obj.side_effect = validate_span

    with mock.patch(
        'pyramid_zipkin.request_helper.generate_random_64bit_string'
    ) as mock_generate_random_64bit_string:
        mock_generate_random_64bit_string.return_value = '1'
        WebTestApp(main({}, **settings)).get('/sample', status=200)

    assert thrift_obj.call_count == 1


def test_upstream_zipkin_headers_sampled(thrift_obj, default_trace_id_generator):
    settings = {'zipkin.trace_id_generator': default_trace_id_generator}

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

    thrift_obj.side_effect = validate

    WebTestApp(main({}, **settings)).get(
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


def test_unsampled_request_has_no_span(thrift_obj, default_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 0,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }

    WebTestApp(main({}, **settings)).get('/sample', status=200)

    assert thrift_obj.call_count == 0


def test_blacklisted_route_has_no_span(thrift_obj, default_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
        'zipkin.blacklisted_routes': ['sample_route'],
    }

    WebTestApp(main({}, **settings)).get('/sample', status=200)

    assert thrift_obj.call_count == 0


def test_blacklisted_path_has_no_span(thrift_obj, default_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
        'zipkin.blacklisted_paths': [r'^/sample'],
    }

    WebTestApp(main({}, **settings)).get('/sample', status=200)

    assert thrift_obj.call_count == 0


def test_no_transport_handler_throws_error():
    app_main = main({})
    del app_main.registry.settings['zipkin.transport_handler']
    assert 'zipkin.transport_handler' not in app_main.registry.settings

    with pytest.raises(ZipkinError):
        WebTestApp(app_main).get('/sample', status=200)


def test_server_extra_annotations_are_included(
    thrift_obj,
    default_trace_id_generator
):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }

    WebTestApp(main({}, **settings)).get('/sample_v2', status=200)

    assert thrift_obj.call_count == 1
    server_spans = thrift_obj.call_args[0][0]
    assert len(server_spans) == 1
    server_span = server_spans[0]

    # Assert that the annotations logged via debug statements exist
    test_helper.assert_extra_annotations(
        server_span,
        {'bar': 1000000, 'foo': 2000000},
    )
    test_helper.assert_extra_binary_annotations(
        server_span,
        {'ping': 'pong'},
    )


def test_binary_annotations(thrift_obj, default_trace_id_generator):
    def set_extra_binary_annotations(dummy_request, response):
        return {'other': dummy_request.registry.settings['other_attr']}

    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
        'zipkin.set_extra_binary_annotations': set_extra_binary_annotations,
        'other_attr': '42',
    }

    def validate_span(span_objs):
        assert len(span_objs) == 1
        span_obj = span_objs[0]
        # Assert that the only present binary_annotations are ones we expect
        expected_annotations = {
            'http.uri': '/sample',
            'http_uri_qs': '/sample?test=1',
            'response_status_code': '200',
            'other': '42',
        }
        result_span = test_helper.massage_result_span(span_obj)
        for ann in result_span['binary_annotations']:
            assert ann['value'] == expected_annotations.pop(ann['key'])
        assert len(expected_annotations) == 0

    thrift_obj.side_effect = validate_span

    WebTestApp(main({}, **settings)).get('/sample?test=1', status=200)

    assert thrift_obj.call_count == 1


def test_binary_annotations_old_qs(thrift_obj, default_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
        'zipkin.set_old_http_uri_qs': True,
        'other_attr': '42',
    }

    def validate_span(span_objs):
        assert len(span_objs) == 1
        span_obj = span_objs[0]
        # Assert that the only present binary_annotations are ones we expect
        expected_annotations = {
            'http.uri': '/sample',
            'http_uri_qs': '/sample?test=1',
            'http.uri.qs': '/sample?test=1',
            'response_status_code': '200',
        }
        result_span = test_helper.massage_result_span(span_obj)
        for ann in result_span['binary_annotations']:
            assert ann['value'] == expected_annotations.pop(ann['key'])
        assert len(expected_annotations) == 0

    thrift_obj.side_effect = validate_span

    WebTestApp(main({}, **settings)).get('/sample?test=1', status=200)

    assert thrift_obj.call_count == 1


def test_custom_create_zipkin_attr(thrift_obj, default_trace_id_generator):
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

    WebTestApp(main({}, **settings)).get('/sample?test=1', status=200)

    assert custom_create_zipkin_attr.called


def test_report_root_timestamp(thrift_obj, default_trace_id_generator):
    settings = {
        'zipkin.report_root_timestamp': True,
        'zipkin.tracing_percent': 100.0,
    }

    old_time = time.time() * 1000000

    def check_for_timestamp_and_duration(span_objs):
        span_obj = span_objs[0]
        assert span_obj.timestamp > old_time
        assert span_obj.duration > 0

    thrift_obj.side_effect = check_for_timestamp_and_duration
    WebTestApp(main({}, **settings)).get('/sample', status=200)


def test_host_and_port_in_span(thrift_obj, default_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.host': '1.2.2.1',
        'zipkin.port': 1231,
    }

    def validate_span(span_objs):
        assert len(span_objs) == 1
        span_obj = span_objs[0]
        # Assert ipv4 and port match what we expect
        expected_ipv4 = (1 << 24) | (2 << 16) | (2 << 8) | 1
        assert expected_ipv4 == span_obj.annotations[0].host.ipv4
        assert 1231 == span_obj.annotations[0].host.port

    thrift_obj.side_effect = validate_span

    WebTestApp(main({}, **settings)).get('/sample?test=1', status=200)

    assert thrift_obj.call_count == 1
