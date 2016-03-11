import mock

import pytest

from pyramid_zipkin import logging_helper
from pyramid_zipkin.exception import ZipkinError


@pytest.fixture
def context():
    attr = mock.Mock(is_sampled=False)
    request = mock.Mock()
    return logging_helper.ZipkinLoggingContext(
        attr, 'thrift_endpoint', 'log_handler', request)


@mock.patch('pyramid_zipkin.logging_helper.annotation_list_builder',
            autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.binary_annotation_list_builder',
            autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.log_span', autospec=True)
def test_log_service_span_creates_service_annotations_and_logs_span(
        log_sp, binary_ann, ann):
    logging_helper.log_service_span('attr', 'strt', 'end', {'k': 'v'},
                                    'endp', 'X', 'registry')
    ann.assert_called_once_with({'sr': 'strt', 'ss': 'end'}, 'endp')
    binary_ann.assert_called_once_with({'k': 'v'}, 'endp')
    log_sp.assert_called_once_with(
        'attr', 'X', 'registry', ann.return_value, binary_ann.return_value, False)


@mock.patch('pyramid_zipkin.logging_helper.create_span', autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.thrift_obj_in_bytes', autospec=True)
def test_log_span_creates_service_annotations_and_logs_span(
        thrift_obj, create_sp):
    registry = {'zipkin.transport_handler': (lambda x, y: None)}
    logging_helper.log_span('attr', 'X', registry, 'ann', 'bann', 'is_client')
    create_sp.assert_called_once_with('attr', 'X', 'ann', 'bann', 'is_client')
    thrift_obj.assert_called_once_with(create_sp.return_value)


@mock.patch('pyramid_zipkin.logging_helper.zipkin_logger', autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.push_zipkin_attrs',
            autospec=True)
def test_zipkin_logging_context_adds_log_handler_on_entry(
        set_mock, logger, context):
    context.__enter__()
    logger.addHandler.assert_called_once_with(context.handler)


@mock.patch('pyramid_zipkin.logging_helper.zipkin_logger', autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.push_zipkin_attrs',
            autospec=True)
def test_zipkin_logging_context_appends_zikin_attr_to_thread_local_on_entry(
        set_mock, logger, context):
    context.__enter__()
    set_mock.assert_called_once_with(context.zipkin_attrs)


@mock.patch('pyramid_zipkin.logging_helper.zipkin_logger', autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.push_zipkin_attrs',
            autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.time.time', autospec=True)
def test_zipkin_logging_context_stores_start_timestamp_on_entry(
        time_mock, set_mock, logger, context):
    time_mock.return_value = 42
    context.__enter__()
    assert 42 == context.start_timestamp


@mock.patch('pyramid_zipkin.logging_helper.zipkin_logger', autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.pop_zipkin_attrs',
            autospec=True)
def test_zipkin_logging_context_pops_zikin_attr_from_thread_local_on_exit(
        pop_mock, logger, context):
    context.__exit__('_', '_', '_')
    pop_mock.assert_called_once_with()


@mock.patch('pyramid_zipkin.logging_helper.zipkin_logger', autospec=True)
def test_zipkin_logging_context_removes_log_handler_on_exit(
        logger, context):
    context.__exit__('_', '_', '_')
    logger.removeHandler.assert_called_once_with(context.handler)


@mock.patch('pyramid_zipkin.logging_helper.zipkin_logger', autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.log_service_span',
            autospec=True)
def test_zipkin_logging_context_doesnt_log_if_span_not_sampled(
        log_span, _, context):
    context.__exit__('_', '_', '_')
    assert 0 == log_span.call_count


def test_zipkin_logging_context_logs_client_span_if_sampled_and_success(
        context):
    # Tests that client spans collected in a ZipkinLoggingContext get properly
    # logged.
    _assert_logged_client_spans(context, None, 'thrift_endpoint')


@mock.patch('pyramid_zipkin.logging_helper.copy_endpoint_with_new_service_name',
            autospec=True)
def test_zipkin_logging_context_logs_client_span_with_new_endpoint_name(
        copy_endpoint, context):
    # Tests that client spans collected in a ZipkinLoggingContext get properly
    # logged with new "service_name" attribute.
    copy_endpoint.return_value = 'new_thrift_endpoint'
    _assert_logged_client_spans(context, 'blargh', 'new_thrift_endpoint')


@mock.patch('pyramid_zipkin.logging_helper.annotation_list_builder',
            autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.binary_annotation_list_builder',
            autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.create_span', autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.thrift_obj_in_bytes', autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.log_service_span', autospec=True)
def _assert_logged_client_spans(
        logging_context, service_name, thrift_endpoint_mock,
        log_span, thrift_obj, create_sp, binary_ann, ann):
    # Sets a bunch of state on the ZipkinLoggingContext, creates some captured
    # client spans, and asserts that these spans were properly logged.
    logging_context.start_timestamp = 24
    logging_context.response_status_code = 200
    logging_context.registry_settings = {
            'zipkin.transport_handler': (lambda x, y: None)}
    spans = [{
        'annotations': 'ann1', 'binary_annotations': 'bann1',
        'span_name': 'foo', 'is_client': False,
        'service_name': service_name,
    }]
    logging_context.handler = mock.Mock(spans=spans)
    logging_context.zipkin_attrs.is_sampled = True
    logging_context.log_spans()
    ann.assert_called_once_with('ann1', thrift_endpoint_mock)
    binary_ann.assert_called_once_with('bann1', thrift_endpoint_mock)
    create_sp.assert_called_once_with(
        logging_context.zipkin_attrs, 'foo', ann.return_value,
        binary_ann.return_value, False)
    thrift_obj.assert_called_once_with(create_sp.return_value)


@mock.patch('pyramid_zipkin.logging_helper.zipkin_logger', autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.time.time', autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.log_service_span', autospec=True)
def test_zipkin_logging_context_logs_service_span_if_sampled_and_success(
        log_span, time, _, context):
    context.start_timestamp = 24
    context.response_status_code = 200
    context.handler = mock.Mock(spans=[])
    context.binary_annotations_dict = {'k': 'v'}
    time.return_value = 42
    context.zipkin_attrs.is_sampled = True
    context.request_method = "get"
    context.request_path = "/foo"
    context.log_spans()
    log_span.assert_called_once_with(
        context.zipkin_attrs, 24, 42, context.binary_annotations_dict,
        'thrift_endpoint', "get /foo",
        context.registry_settings)


def test_zipkin_handler_init():
    handler = logging_helper.ZipkinLoggerHandler('foo')
    assert handler.zipkin_attrs == 'foo'


def test_zipkin_handler_does_not_emit_unsampled_record(unsampled_zipkin_attr):
    handler = logging_helper.ZipkinLoggerHandler(unsampled_zipkin_attr)
    assert not handler.emit('bla')


@mock.patch.object(logging_helper.ZipkinLoggerHandler, 'store_span')
def test_zipkin_handler_successfully_emits_sampled_record(
        store_sp, sampled_zipkin_attr):
    record = mock.Mock()
    record.msg = {'annotations': 'ann1', 'binary_annotations': 'bann1',
                  'name': 'foo', 'type': 'service',
                  'service_name': 'blargh'}
    handler = logging_helper.ZipkinLoggerHandler(sampled_zipkin_attr)
    handler.emit(record)
    store_sp.assert_called_once_with('foo', False, 'ann1', 'bann1', 'blargh')


def test_store_span_appends_to_span():
    handler = logging_helper.ZipkinLoggerHandler('foo')
    handler.store_span('a', False, {'foo': 2}, {'bar': 'baz'}, None)
    assert handler.spans == [{'annotations': {'foo': 2},
                              'binary_annotations': {'bar': 'baz'},
                              'span_name': 'a',
                              'is_client': False,
                              'service_name': None}]


def test_zipkin_handler_raises_exception_if_ann_and_bann_not_provided(
        sampled_zipkin_attr):
    record = mock.Mock(msg={'name': 'foo'})
    handler = logging_helper.ZipkinLoggerHandler(sampled_zipkin_attr)
    with pytest.raises(ZipkinError) as excinfo:
        handler.emit(record)
    assert ("Atleast one of annotation/binary annotation has to be provided"
            " for foo span" == str(excinfo.value))


@mock.patch('pyramid_zipkin.logging_helper.create_span', autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.thrift_obj_in_bytes', autospec=True)
def test_log_span_calls_transport_handler_with_correct_params(thrift_obj,
                                                              create_sp):
    transport_handler = mock.Mock()
    registry = {'zipkin.transport_handler': transport_handler,
                'zipkin.stream_name': 'foo'}
    logging_helper.log_span('attr', 'X', registry, 'ann', 'bann', 'is_client')
    transport_handler.assert_called_once_with('foo', thrift_obj.return_value)


@mock.patch('pyramid_zipkin.logging_helper.create_span', autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.thrift_obj_in_bytes', autospec=True)
def test_log_span_uses_default_stream_name_if_not_provided(thrift_obj, create_sp):
    transport_handler = mock.Mock()
    registry = {'zipkin.transport_handler': transport_handler}
    logging_helper.log_span('attr', 'X', registry, 'ann', 'bann', 'is_client')
    transport_handler.assert_called_once_with('zipkin', thrift_obj.return_value)


@mock.patch('pyramid_zipkin.logging_helper.create_span', autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.thrift_obj_in_bytes', autospec=True)
def test_log_span_raises_error_if_handler_not_defined(thrift_obj, create_sp):
    registry = {'zipkin.stream_name': 'foo'}
    with pytest.raises(ZipkinError) as excinfo:
        logging_helper.log_span('attr', 'X', registry, 'ann', 'bann', '_')
    assert ("`zipkin.transport_handler` is a required config property" in str(
        excinfo.value))


def test_get_binary_annotations():
    def set_extra_binary_annotations(req, resp):
        return {'k': 'v'}
    registry = mock.Mock(
        settings={
            'zipkin.set_extra_binary_annotations': set_extra_binary_annotations
        })
    request = mock.Mock(path='/path', path_qs='/path?time=now')
    request.registry = registry
    response = mock.Mock()

    annotations = logging_helper.get_binary_annotations(request, response)
    expected = {'http.uri': '/path', 'http.uri.qs': '/path?time=now', 'k': 'v'}
    assert annotations == expected

    # Try it again with no callback specified
    request.registry.settings = {}
    del expected['k']
    annotations = logging_helper.get_binary_annotations(request, response)
    assert annotations == expected
