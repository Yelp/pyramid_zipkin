import mock

from pyramid.request import Request

from pyramid_zipkin import zipkin
from pyramid_zipkin.logging_helper import ZipkinLoggerHandler
from pyramid_zipkin.request_helper import ZipkinAttrs
from pyramid_zipkin.thread_local import get_zipkin_attrs


@mock.patch('pyramid_zipkin.zipkin.ZipkinLoggingContext', autospec=True)
@mock.patch('pyramid_zipkin.zipkin.create_zipkin_attr', autospec=True)
@mock.patch('pyramid_zipkin.zipkin.create_endpoint', autospec=True)
@mock.patch('pyramid_zipkin.zipkin.get_binary_annotations', autospec=True)
def _test_zipkin_context(
        binann_mock, endp_mock, attrs_mock, context, is_sampled):
    instance = context.return_value
    attrs_mock.return_value = ZipkinAttrs(
        'trace_id', 'span_id', 'parent_span_id', 'flags', is_sampled)
    binann_mock.return_value = {'k': 'v'}
    endp_mock.return_value = 'thrift_endpoint'
    tween = zipkin.zipkin_tween(mock.Mock(), 'registry')
    tween(mock.Mock())
    return instance


def test_tween_is_not_wrapped_by_zipkin_logging_context():
    instance = _test_zipkin_context(is_sampled=False)
    assert not instance.__enter__.called
    assert not instance.__exit__.called


def test_tween_is_wrapped_by_zipkin_logging_context():
    instance = _test_zipkin_context(is_sampled=True)
    instance.__enter__.assert_called_once_with()
    instance.__exit__.assert_called_once_with(None, None, None)


@mock.patch('pyramid_zipkin.request_helper.is_tracing', autospec=True)
def test_tween_not_sampled_sets_zipkin_trace_id(is_tracing_mock):
    # Tests that even in the unsampled case, the zipkin tween sets
    # the zipkin_trace_id attr on the request.
    is_tracing_mock.return_value = False
    assert get_zipkin_attrs() is None
    request = Request.blank('/', headers={'X-B3-TraceId': 'deadbeefdeadbeef'})
    tween = zipkin.zipkin_tween(mock.Mock(), 'registry')
    tween(request)
    assert request.zipkin_trace_id == 'deadbeefdeadbeef'
    # Make sure the tween doesn't leave zipkin attrs on threadlocal storage
    assert get_zipkin_attrs() is None


@mock.patch('pyramid_zipkin.zipkin.get_zipkin_attrs', autospec=True)
def test_create_headers_for_new_span_empty_if_no_active_request(get_mock):
    get_mock.return_value = None
    assert {} == zipkin.create_headers_for_new_span()


@mock.patch('pyramid_zipkin.zipkin.get_zipkin_attrs', autospec=True)
@mock.patch('pyramid_zipkin.zipkin.generate_random_64bit_string', autospec=True)
def test_create_headers_for_new_span_returns_header_if_active_request(
        gen_mock, get_mock):
    get_mock.return_value = mock.Mock(
        trace_id='27133d482ba4f605', span_id='37133d482ba4f605', is_sampled=True)
    gen_mock.return_value = '17133d482ba4f605'
    expected = {
        'X-B3-TraceId': '27133d482ba4f605',
        'X-B3-SpanId': '17133d482ba4f605',
        'X-B3-ParentSpanId': '37133d482ba4f605',
        'X-B3-Flags': '0',
        'X-B3-Sampled': '1',
    }
    assert expected == zipkin.create_headers_for_new_span()


@mock.patch('pyramid_zipkin.zipkin.pop_zipkin_attrs', autospec=True)
@mock.patch('pyramid_zipkin.zipkin.push_zipkin_attrs', autospec=True)
@mock.patch('pyramid_zipkin.zipkin.get_zipkin_attrs', autospec=True)
def test_span_context_no_zipkin_attrs(
    get_zipkin_attrs_mock,
    push_zipkin_attrs_mock,
    pop_zipkin_attrs_mock,
):
    # When not in a Zipkin context, don't do anything
    get_zipkin_attrs_mock.return_value = None
    context = zipkin.SpanContext('svc', 'span')
    with context:
        pass
    assert not pop_zipkin_attrs_mock.called
    assert not push_zipkin_attrs_mock.called


@mock.patch('pyramid_zipkin.zipkin.pop_zipkin_attrs', autospec=True)
@mock.patch('pyramid_zipkin.zipkin.push_zipkin_attrs', autospec=True)
@mock.patch('pyramid_zipkin.zipkin.get_zipkin_attrs', autospec=True)
def test_span_context_not_sampled(
    get_zipkin_attrs_mock,
    push_zipkin_attrs_mock,
    pop_zipkin_attrs_mock,
):
    # When ZipkinAttrs say this request isn't sampled, push new attrs
    # onto threadlocal stack, but do nothing else.
    get_zipkin_attrs_mock.return_value = ZipkinAttrs(
        'trace_id', 'span_id', 'parent_span_id', 'flags', False)
    context = zipkin.SpanContext('svc', 'span')
    with context:
        pass
    # Even in the not-sampled case, if the client context generates
    # new zipkin attrs, it should pop them off.
    assert pop_zipkin_attrs_mock.called
    assert push_zipkin_attrs_mock.called


@mock.patch('pyramid_zipkin.thread_local._thread_local', autospec=True)
@mock.patch('pyramid_zipkin.zipkin.generate_random_64bit_string', autospec=True)
@mock.patch('pyramid_zipkin.zipkin.zipkin_logger', autospec=True)
def test_span_context_sampled_no_handlers(
    zipkin_logger_mock,
    generate_string_mock,
    thread_local_mock,
):
    zipkin_attrs = ZipkinAttrs(
        'trace_id', 'span_id', 'parent_span_id', 'flags', True)
    thread_local_mock.requests = [zipkin_attrs]

    zipkin_logger_mock.handlers = []
    generate_string_mock.return_value = '1'

    context = zipkin.SpanContext('svc', 'span')
    with context:
        # Assert that the new ZipkinAttrs were saved
        new_zipkin_attrs = get_zipkin_attrs()
        assert new_zipkin_attrs.span_id == '1'

    # Outside of the context, things should be returned to normal
    assert get_zipkin_attrs() == zipkin_attrs


@mock.patch('pyramid_zipkin.thread_local._thread_local', autospec=True)
@mock.patch('pyramid_zipkin.zipkin.generate_random_64bit_string', autospec=True)
@mock.patch('pyramid_zipkin.zipkin.zipkin_logger', autospec=True)
def test_span_context(
    zipkin_logger_mock,
    generate_string_mock,
    thread_local_mock,
):
    zipkin_attrs = ZipkinAttrs(
        'trace_id', 'span_id', 'parent_span_id', 'flags', True)
    thread_local_mock.requests = [zipkin_attrs]
    logging_handler = ZipkinLoggerHandler(zipkin_attrs)
    assert logging_handler.parent_span_id is None
    assert logging_handler.client_spans == []

    zipkin_logger_mock.handlers = [logging_handler]
    generate_string_mock.return_value = '1'

    context = zipkin.SpanContext(
        service_name='svc',
        span_name='span',
        annotations={'something': 1},
        binary_annotations={'foo': 'bar'},
    )
    with context:
        # Assert that the new ZipkinAttrs were saved
        new_zipkin_attrs = get_zipkin_attrs()
        assert new_zipkin_attrs.span_id == '1'
        # And that the logging handler has a parent_span_id
        assert logging_handler.parent_span_id == '1'

    # Outside of the context, things should be returned to normal,
    # except a new client span is saved in the handler
    assert logging_handler.parent_span_id is None
    assert get_zipkin_attrs() == zipkin_attrs

    client_span = logging_handler.client_spans.pop()
    assert logging_handler.client_spans == []
    # These reserved annotations are based on timestamps so pop em.
    # This also acts as a check that they exist.
    for annotation in ('cs', 'cr', 'ss', 'sr'):
        client_span['annotations'].pop(annotation)

    expected_client_span = {
        'span_name': 'span',
        'service_name': 'svc',
        'parent_span_id': None,
        'span_id': '1',
        'annotations': {'something': 1},
        'binary_annotations': {'foo': 'bar'},
    }
    assert client_span == expected_client_span
