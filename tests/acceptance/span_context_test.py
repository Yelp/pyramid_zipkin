import json

import mock
from webtest import TestApp as WebTestApp

from tests.acceptance.test_helper import generate_app_main


def test_log_new_client_spans(default_trace_id_generator):
    # Tests that log lines with 'service_name' keys are logged as
    # new client spans.
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }
    app_main, transport, _ = generate_app_main(settings)

    WebTestApp(app_main).get('/sample_v2_client', status=200)

    assert len(transport.output) == 1
    span_list = json.loads(transport.output[0])
    assert len(span_list) == 3
    foo_span = span_list[0]
    bar_span = span_list[1]
    server_span = span_list[2]

    # Some sanity checks on the new client spans
    for client_span in (foo_span, bar_span):
        assert client_span['parentId'] == server_span['id']
    assert foo_span['id'] != bar_span['id']
    assert foo_span['annotations'] == [
        {'timestamp': 2000000, 'value': 'foo_client'},
    ]
    assert bar_span['annotations'] == [
        {'timestamp': 1000000, 'value': 'bar_client'},
    ]


@mock.patch('pyramid_zipkin.request_helper.generate_random_64bit_string')
def test_headers_created_for_sampled_child_span(
    mock_generate_string,
    default_trace_id_generator
):
    # Simple smoke test for create_headers_for_new_span
    mock_generate_string.return_value = '17133d482ba4f605'
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }

    _assert_headers_present(settings, is_sampled='1')


@mock.patch('pyramid_zipkin.request_helper.generate_random_64bit_string')
def test_headers_created_for_unsampled_child_span(
    mock_generate_string,
    default_trace_id_generator,
):
    # Headers are still created if the span is unsampled
    mock_generate_string.return_value = '17133d482ba4f605'
    settings = {
        'zipkin.tracing_percent': 0,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }
    _assert_headers_present(settings, is_sampled='0')


def _assert_headers_present(settings, is_sampled):
    # Helper method for smoke testing proper setting of headers.
    # TraceId and ParentSpanId are set by default_trace_id_generator
    # and mock_generate_string in upstream test methods.
    expected = {
        'X-B3-Flags': '0',
        'X-B3-ParentSpanId': '17133d482ba4f605',
        'X-B3-Sampled': is_sampled,
        'X-B3-TraceId': '17133d482ba4f605',
    }

    app_main, _, _ = generate_app_main(settings)
    headers = WebTestApp(app_main).get('/sample_child_span',
                                       status=200)
    headers_json = headers.json
    headers_json.pop('X-B3-SpanId')  # Randomly generated - Ignore.

    assert expected == headers_json


def test_span_context(default_trace_id_generator):
    # Tests that log lines with 'service_name' keys are logged as
    # new client spans.
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }
    app_main, transport, _ = generate_app_main(settings)

    WebTestApp(app_main).get('/span_context', status=200)

    # Spans are batched
    # The order of span logging goes from innermost (grandchild) up.
    assert len(transport.output) == 1
    span_list = json.loads(transport.output[0])
    assert len(span_list) == 3
    grandchild_span = span_list[0]
    child_span = span_list[1]
    server_span = span_list[2]

    # Assert proper hierarchy
    assert child_span['parentId'] == server_span['id']
    assert grandchild_span['parentId'] == child_span['id']
    # Assert annotations are properly assigned
    assert child_span['annotations'] == [
        {'timestamp': 1000000, 'value': 'child_annotation'},
    ]
    assert child_span['tags'] == {'foo': 'bar', 'child': 'true'}
    assert grandchild_span['annotations'] == [
        {'timestamp': 1000000, 'value': 'grandchild_annotation'},
    ]
    assert grandchild_span['tags'] == {'grandchild': 'true'}


def test_decorator(default_trace_id_generator):
    # Tests that log lines with 'service_name' keys are logged as
    # new client spans.
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }
    app_main, transport, _ = generate_app_main(settings)

    WebTestApp(app_main).get('/decorator_context', status=200)

    # Two spans are logged - child span, then server span
    assert len(transport.output) == 1
    span_list = json.loads(transport.output[0])
    assert len(span_list) == 2
    child_span = span_list[0]
    server_span = span_list[1]

    # Assert proper hierarchy and annotations
    assert child_span['parentId'] == server_span['id']
    assert child_span['tags'] == {'a': '1'}
    assert child_span['name'] == 'my_span'


def test_add_logging_annotation():
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.add_logging_annotation': True,
    }
    app_main, transport, _ = generate_app_main(settings)

    WebTestApp(app_main).get('/sample', status=200)

    assert len(transport.output) == 1
    span_list = json.loads(transport.output[0])
    assert len(span_list) == 1
    server_span = span_list[0]

    # Just make sure py-zipkin added an annotation for when logging started
    assert server_span['annotations'] == [
        {'timestamp': mock.ANY, 'value': 'py_zipkin.logging_end'},
    ]
