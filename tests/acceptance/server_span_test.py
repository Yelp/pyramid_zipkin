# -*- coding: utf-8 -*-
import time

import mock
import pytest
from py_zipkin.exception import ZipkinError
from py_zipkin.util import unsigned_hex_to_signed_int
from webtest import TestApp

from .app import main
from tests.acceptance import test_helper


@mock.patch('py_zipkin.logging_helper.thrift_obj_in_bytes', autospec=True)
def test_sample_server_span_with_100_percent_tracing(
        thrift_obj, default_trace_id_generator, get_span):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }

    old_time = time.time() * 1000000

    def validate_span(span_obj):
        result_span = test_helper.massage_result_span(span_obj)
        timestamps = test_helper.get_timestamps(result_span)
        get_span['trace_id'] = unsigned_hex_to_signed_int(
            default_trace_id_generator(span_obj),
        )
        assert get_span == result_span
        assert old_time <= timestamps['sr']
        assert timestamps['sr'] <= timestamps['ss']

    thrift_obj.side_effect = validate_span

    with mock.patch(
        'pyramid_zipkin.request_helper.generate_random_64bit_string'
    ) as mock_generate_random_64bit_string:
        mock_generate_random_64bit_string.return_value = '1'
        TestApp(main({}, **settings)).get('/sample', status=200)

    assert thrift_obj.call_count == 1


@mock.patch('py_zipkin.logging_helper.thrift_obj_in_bytes', autospec=True)
def test_unsampled_request_has_no_span(thrift_obj, default_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 0,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }

    TestApp(main({}, **settings)).get('/sample', status=200)

    assert thrift_obj.call_count == 0


@mock.patch('py_zipkin.logging_helper.thrift_obj_in_bytes', autospec=True)
def test_blacklisted_route_has_no_span(thrift_obj, default_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
        'zipkin.blacklisted_routes': ['sample_route'],
    }

    TestApp(main({}, **settings)).get('/sample', status=200)

    assert thrift_obj.call_count == 0


@mock.patch('py_zipkin.logging_helper.thrift_obj_in_bytes', autospec=True)
def test_blacklisted_path_has_no_span(thrift_obj, default_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
        'zipkin.blacklisted_paths': [r'^/sample'],
    }

    TestApp(main({}, **settings)).get('/sample', status=200)

    assert thrift_obj.call_count == 0


def test_no_transport_handler_throws_error():
    app_main = main({})
    del app_main.registry.settings['zipkin.transport_handler']
    assert 'zipkin.transport_handler' not in app_main.registry.settings

    with pytest.raises(ZipkinError):
        TestApp(app_main).get('/sample', status=200)


@mock.patch('py_zipkin.logging_helper.thrift_obj_in_bytes', autospec=True)
def test_server_extra_annotations_are_included(
    thrift_obj,
    default_trace_id_generator
):
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }

    TestApp(main({}, **settings)).get('/sample_v2', status=200)

    assert thrift_obj.call_count == 1
    server_span = thrift_obj.call_args[0][0]
    # Assert that the annotations logged via debug statements exist
    test_helper.assert_extra_annotations(
        server_span,
        {'bar': 1000000, 'foo': 2000000},
    )
    test_helper.assert_extra_binary_annotations(
        server_span,
        {'ping': 'pong'},
    )


@mock.patch('py_zipkin.logging_helper.thrift_obj_in_bytes', autospec=True)
def test_binary_annotations(thrift_obj, default_trace_id_generator):
    def set_extra_binary_annotations(dummy_request, response):
        return {'other': dummy_request.registry.settings['other_attr']}

    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
        'zipkin.set_extra_binary_annotations': set_extra_binary_annotations,
        'other_attr': '42',
    }

    def validate_span(span_obj):
        # Assert that the only present binary_annotations are ones we expect
        expected_annotations = {
            'http.uri': '/sample',
            'http.uri.qs': '/sample?test=1',
            'response_status_code': '200',
            'other': '42',
        }
        result_span = test_helper.massage_result_span(span_obj)
        for ann in result_span['binary_annotations']:
            assert ann['value'] == expected_annotations.pop(ann['key'])
        assert len(expected_annotations) == 0

    thrift_obj.side_effect = validate_span

    TestApp(main({}, **settings)).get('/sample?test=1', status=200)

    assert thrift_obj.call_count == 1
