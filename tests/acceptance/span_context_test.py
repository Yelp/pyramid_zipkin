import mock
from webtest import TestApp

from .app import main
from tests.acceptance.test_helper import assert_extra_annotations
from tests.acceptance.test_helper import assert_extra_binary_annotations


@mock.patch('py_zipkin.logging_helper.thrift_obj_in_bytes', autospec=True)
def test_log_new_client_spans(
    thrift_obj,
    default_trace_id_generator
):
    # Tests that log lines with 'service_name' keys are logged as
    # new client spans.
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }

    TestApp(main({}, **settings)).get('/sample_v2_client', status=200)

    # Ugly extraction of spans from mock thrift_obj call args
    foo_span_args, bar_span_args, server_span_args = thrift_obj.call_args_list
    foo_span = foo_span_args[0][0]
    bar_span = bar_span_args[0][0]
    server_span = server_span_args[0][0]
    # Some sanity checks on the new client spans
    for client_span in (foo_span, bar_span):
        assert client_span.parent_id == server_span.id
    assert foo_span.id != bar_span.id
    assert_extra_annotations(foo_span, {'foo_client': 2000000})
    assert_extra_annotations(bar_span, {'bar_client': 1000000})


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
    # Headers are still created if the span is unsampled.
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

    headers = TestApp(main({}, **settings)).get('/sample_child_span',
                                                status=200)
    headers_json = headers.json
    headers_json.pop('X-B3-SpanId')  # Randomly generated - Ignore.

    assert expected == headers_json


@mock.patch('py_zipkin.logging_helper.thrift_obj_in_bytes', autospec=True)
def test_span_context(
    thrift_obj,
    default_trace_id_generator
):
    # Tests that log lines with 'service_name' keys are logged as
    # new client spans.
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }

    TestApp(main({}, **settings)).get('/span_context', status=200)

    # Ugly extraction of spans from mock thrift_obj call args
    # The order of span logging goes from innermost (grandchild) up.
    gc_span_args, child_span_args, server_span_args = thrift_obj.call_args_list
    child_span = child_span_args[0][0]
    grandchild_span = gc_span_args[0][0]
    server_span = server_span_args[0][0]
    # Assert proper hierarchy
    assert child_span.parent_id == server_span.id
    assert grandchild_span.parent_id == child_span.id
    # Assert annotations are properly assigned
    assert_extra_annotations(server_span, {'server_annotation': 1000000})
    assert_extra_binary_annotations(server_span, {'server': 'true'})
    assert_extra_annotations(child_span, {'child_annotation': 1000000})
    assert_extra_binary_annotations(
        child_span, {'foo': 'bar', 'child': 'true'})
    assert_extra_annotations(
        grandchild_span, {'grandchild_annotation': 1000000})
    assert_extra_binary_annotations(grandchild_span, {'grandchild': 'true'})

    # For the span produced by SpanContext, assert cs==sr and ss==cr
    # Initialize them all so the equalities won't be true.
    annotations = {
        'cs': 0, 'sr': 1, 'ss': 2, 'cr': 3
    }
    for annotation in child_span.annotations:
        if annotation.value in annotations:
            annotations[annotation.value] = annotation.timestamp
    assert annotations['cs'] == annotations['sr']
    assert annotations['ss'] == annotations['cr']


@mock.patch('py_zipkin.logging_helper.thrift_obj_in_bytes', autospec=True)
def test_decorator(
    thrift_obj,
    default_trace_id_generator
):
    # Tests that log lines with 'service_name' keys are logged as
    # new client spans.
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }

    TestApp(main({}, **settings)).get('/decorator_context', status=200)

    # Two spans are logged - child span, then server span
    child_span_args, server_span_args = thrift_obj.call_args_list
    child_span = child_span_args[0][0]
    server_span = server_span_args[0][0]
    # Assert proper hierarchy and annotations
    assert child_span.parent_id == server_span.id
    assert_extra_binary_annotations(child_span, {'a': '1'})
    assert child_span.name == 'my_span'
