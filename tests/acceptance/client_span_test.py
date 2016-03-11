import mock

from webtest import TestApp

from .app import main
from tests.acceptance import test_helper


@mock.patch('pyramid_zipkin.logging_helper.thrift_obj_in_bytes', autospec=True)
def test_client_ann_are_logged_as_new_spans(thrift_obj,
                                            sampled_trace_id_generator):
    settings = {
        'zipkin.trace_id_generator': sampled_trace_id_generator,
    }

    def validate_span_foo(span_obj):
        result_span = test_helper.massage_result_span(span_obj)
        assert 1 != result_span['id']  # id is a new span id
        assert 1 == result_span['parent_id']  # old id becomes parent.
        ann = result_span['annotations'][0]
        assert ('foo_client', 2000000) == (ann['value'], ann['timestamp'])

    def validate_span_bar(span_obj):
        result_span = test_helper.massage_result_span(span_obj)
        assert 1 != result_span['id']  # id is a new span id
        assert 1 == result_span['parent_id']  # old id becomes parent.
        ann = result_span['annotations'][0]
        assert ('bar_client', 1000000) == (ann['value'], ann['timestamp'])

    thrift_obj.side_effect = [lambda _: None,  # first span is sr, ss - ignore
                              validate_span_foo,
                              validate_span_bar]

    TestApp(main({}, **settings)).get('/sample_v2_client', status=200)

    assert thrift_obj.call_count == 3


def test_headers_created_for_sampled_child_span(sampled_trace_id_generator):
    settings = {
        'zipkin.trace_id_generator': sampled_trace_id_generator,
    }

    expected = {
        'X-B3-Flags': '0',
        'X-B3-ParentSpanId': '17133d482ba4f605',
        'X-B3-Sampled': '1',
        'X-B3-TraceId': '0000000000000000',
    }

    with mock.patch(
        'pyramid_zipkin.request_helper.generate_random_64bit_string'
    ) as mock_generate_random_64bit_string:
        mock_generate_random_64bit_string.return_value = '17133d482ba4f605'
        headers = TestApp(main({}, **settings)).get('/sample_child_span',
                                                    status=200)
    headers_json = headers.json
    headers_json.pop('X-B3-SpanId')  # Randomly generated - Ignore.

    assert expected == headers_json


def test_headers_not_created_for_unsampled_child_span(default_trace_id_generator):
    settings = {
        'zipkin.tracing_percent': 0,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }

    headers = TestApp(main({}, **settings)).get('/sample_child_span',
                                                status=200)
    headers_json = headers.json

    assert {} == headers_json
