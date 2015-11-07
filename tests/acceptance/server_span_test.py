# -*- coding: utf-8 -*-
import mock
import time

from webtest import TestApp

from .app import main
from tests.acceptance import test_helper
from pyramid_zipkin.thrift_helper import get_id


@mock.patch('pyramid_zipkin.logging_helper.base64_thrift', autospec=True)
def test_sample_server_span_with_100_percent_tracing(
        b64_thrift, default_trace_id_generator, get_span):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }

    old_time = time.time() * 1000000

    def validate_span(span_obj):
        result_span = test_helper.massage_result_span(span_obj)
        timestamps = test_helper.get_timestamps(result_span)
        get_span['trace_id'] = get_id(default_trace_id_generator(span_obj))
        assert get_span == result_span
        assert old_time <= timestamps['sr']
        assert timestamps['sr'] <= timestamps['ss']

    b64_thrift.side_effect = validate_span

    TestApp(main({}, **settings)).get('/sample', status=200)

    assert b64_thrift.call_count == 1


@mock.patch('pyramid_zipkin.logging_helper.base64_thrift', autospec=True)
def test_sample_server_span_with_specific_trace_id_which_samples(
        b64_thrift, sampled_trace_id_generator):
    settings = {
        'zipkin.trace_id_generator': sampled_trace_id_generator,
    }

    TestApp(main({}, **settings)).get('/sample', status=200)

    assert b64_thrift.call_count == 1


@mock.patch('pyramid_zipkin.logging_helper.base64_thrift', autospec=True)
def test_no_sample_server_span_happens_for_500_response(
        b64_thrift, default_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }

    TestApp(main({}, **settings)).get('/server_error', status=500)

    assert b64_thrift.call_count == 0


@mock.patch('pyramid_zipkin.logging_helper.base64_thrift', autospec=True)
def test_no_sample_server_span_happens_for_400_response(
        b64_thrift, default_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }

    TestApp(main({}, **settings)).get('/client_error', status=400)

    assert b64_thrift.call_count == 0


@mock.patch('pyramid_zipkin.logging_helper.base64_thrift', autospec=True)
def test_unsampled_request_has_no_span(b64_thrift, default_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 0,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }

    TestApp(main({}, **settings)).get('/sample', status=200)

    assert b64_thrift.call_count == 0


@mock.patch('pyramid_zipkin.logging_helper.base64_thrift', autospec=True)
def test_blacklisted_route_has_no_span(b64_thrift, sampled_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': sampled_trace_id_generator,
        'zipkin.blacklisted_routes': ['sample_route'],
    }

    TestApp(main({}, **settings)).get('/sample', status=200)

    assert b64_thrift.call_count == 0


@mock.patch('pyramid_zipkin.logging_helper.base64_thrift', autospec=True)
def test_blacklisted_path_has_no_span(b64_thrift, sampled_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': sampled_trace_id_generator,
        'zipkin.blacklisted_paths': [r'^/sample'],
    }

    TestApp(main({}, **settings)).get('/sample', status=200)

    assert b64_thrift.call_count == 0


@mock.patch('pyramid_zipkin.logging_helper.base64_thrift', autospec=True)
def test_server_extra_annotations_are_loggd(b64_thrift,
                                            sampled_trace_id_generator):
    settings = {
        'zipkin.trace_id_generator': sampled_trace_id_generator,
    }

    def validate_span(span_obj):
        result_span = test_helper.massage_result_span(span_obj)
        if result_span['name'] == 'v2':
            assert (1, 0) == (result_span['id'], result_span['parent_id'])
            bar_ann = result_span['annotations'][0]
            assert ('bar', 1000000) == (bar_ann['value'], bar_ann['timestamp'])
            foo_ann = result_span['annotations'][1]
            assert ('foo', 2000000) == (foo_ann['value'], foo_ann['timestamp'])
            b_ann = result_span['binary_annotations'][0]
            assert ('ping', 'pong') == (b_ann['key'], b_ann['value'])

    b64_thrift.side_effect = validate_span

    TestApp(main({}, **settings)).get('/sample_v2', status=200)

    assert b64_thrift.call_count == 2
