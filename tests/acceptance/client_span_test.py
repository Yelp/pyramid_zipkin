import mock

from webtest import TestApp

from .app import main
from tests.acceptance.test_helper import assert_extra_annotations
from tests.acceptance.test_helper import assert_extra_binary_annotations


@mock.patch('pyramid_zipkin.logging_helper.thrift_obj_in_bytes', autospec=True)
def test_log_new_client_spans(
    thrift_obj,
    sampled_trace_id_generator
):
    # Tests that log lines with 'service_name' keys are logged as
    # new client spans.
    settings = {
        'zipkin.trace_id_generator': sampled_trace_id_generator,
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


@mock.patch('pyramid_zipkin.request_helper.generate_span_id')
def test_headers_created_for_sampled_child_span(
    mock_generate_span_id,
    sampled_trace_id_generator
):
    # Simple smoke test for create_headers_for_new_span
    mock_generate_span_id.return_value = '0x1234'
    settings = {
        'zipkin.trace_id_generator': sampled_trace_id_generator,
    }

    expected = {
        'X-B3-Flags': '0',
        'X-B3-ParentSpanId': '0x1234',
        'X-B3-Sampled': '1',
        'X-B3-TraceId': '0x0',
    }

    headers = TestApp(main({}, **settings)).get('/sample_child_span',
                                                status=200)
    headers_json = headers.json
    headers_json.pop('X-B3-SpanId')  # Randomly generated - Ignore.

    assert expected == headers_json


def test_headers_not_created_for_unsampled_child_span(default_trace_id_generator):
    # Tests that empty headers are returned if the request isn't sampled
    settings = {
        'zipkin.tracing_percent': 0,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }

    headers = TestApp(main({}, **settings)).get('/sample_child_span',
                                                status=200)
    assert {} == headers.json


@mock.patch('pyramid_zipkin.logging_helper.thrift_obj_in_bytes', autospec=True)
def test_client_context(
    thrift_obj,
    sampled_trace_id_generator
):
    # Tests that log lines with 'service_name' keys are logged as
    # new client spans.
    settings = {
        'zipkin.trace_id_generator': sampled_trace_id_generator,
    }

    TestApp(main({}, **settings)).get('/client_context', status=200)

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
    assert_extra_binary_annotations(child_span, {'foo': 'bar', 'child': 'true'})
    assert_extra_annotations(grandchild_span, {'grandchild_annotation': 1000000})
    assert_extra_binary_annotations(grandchild_span, {'grandchild': 'true'})
