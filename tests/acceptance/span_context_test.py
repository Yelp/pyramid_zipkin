import mock
from webtest import TestApp as WebTestApp

from .app import main
from tests.acceptance.test_helper import assert_extra_annotations
from tests.acceptance.test_helper import assert_extra_binary_annotations
from tests.acceptance.test_helper import decode_thrift
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
    span_list = decode_thrift(transport.output[0])
    assert len(span_list) == 3
    foo_span = span_list[0]
    bar_span = span_list[1]
    server_span = span_list[2]

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

    headers = WebTestApp(main({}, **settings)).get('/sample_child_span',
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
    span_list = decode_thrift(transport.output[0])
    assert len(span_list) == 3
    grandchild_span = span_list[0]
    child_span = span_list[1]
    server_span = span_list[2]

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
    span_list = decode_thrift(transport.output[0])
    assert len(span_list) == 2
    child_span = span_list[0]
    server_span = span_list[1]

    # Assert proper hierarchy and annotations
    assert child_span.parent_id == server_span.id
    assert_extra_binary_annotations(child_span, {'a': '1'})
    assert child_span.name == 'my_span'


def test_add_logging_annotation():
    settings = {
        'zipkin.tracing_percent': 100,
        'zipkin.add_logging_annotation': True,
    }
    app_main, transport, _ = generate_app_main(settings)

    WebTestApp(app_main).get('/sample', status=200)

    assert len(transport.output) == 1
    span_list = decode_thrift(transport.output[0])
    assert len(span_list) == 1
    server_span = span_list[0]

    # Just make sure py-zipkin added an annotation for when logging started
    assert any(
        annotation.value == 'py_zipkin.logging_end'
        for annotation in server_span.annotations
    )
