import mock

import pytest

from pyramid_zipkin import logging_helper
from pyramid_zipkin.exception import ZipkinError


@pytest.fixture
def context():
    attr = mock.Mock(is_sampled=False)
    request = mock.Mock()
    return logging_helper.ZipkinLoggingContext(
        attr, 'endpoint_attrs', 'log_handler', request)


@mock.patch('pyramid_zipkin.logging_helper.annotation_list_builder',
            autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.binary_annotation_list_builder',
            autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.log_span', autospec=True)
def test_log_service_span_creates_service_annotations_and_logs_span(
        log_sp, binary_ann, ann):
    logging_helper.log_service_span('attr', 'strt', 'end', 'path', 'endp', 'X',
                                    'registry')
    ann.assert_called_once_with({'sr': 'strt', 'ss': 'end'}, 'endp')
    binary_ann.assert_called_once_with({'http.uri': 'path'}, 'endp')
    log_sp.assert_called_once_with(
        'attr', 'X', 'registry', ann.return_value, binary_ann.return_value, False)


@mock.patch('pyramid_zipkin.logging_helper.create_span', autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.base64_thrift', autospec=True)
def test_log_span_creates_service_annotations_and_logs_span(
        b64, create_sp):
    registry = {'zipkin.scribe_handler': (lambda x, y: None)}
    logging_helper.log_span('attr', 'X', registry, 'ann', 'bann', 'is_client')
    create_sp.assert_called_once_with('attr', 'X', 'ann', 'bann', 'is_client')
    b64.assert_called_once_with(create_sp.return_value)


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


@mock.patch('pyramid_zipkin.logging_helper.annotation_list_builder',
            autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.binary_annotation_list_builder',
            autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.create_span', autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.base64_thrift', autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.log_service_span', autospec=True)
def test_zipkin_logging_context_logs_annotated_span_if_sampled_and_success(
        log_span, b64, create_sp, binary_ann, ann, context):
    context.start_timestamp = 24
    context.response_status_code = 200
    context.registry_settings = {'zipkin.scribe_handler': (lambda x, y: None)}
    spans = {'foo': {'annotations': 'ann1', 'binary_annotations': 'bann1',
             'span_name': 'foo', 'is_client': False}}
    context.handler = mock.Mock(spans=spans)
    context.zipkin_attrs.is_sampled = True
    context.log_spans()
    ann.assert_called_once_with('ann1', 'endpoint_attrs')
    binary_ann.assert_called_once_with('bann1', 'endpoint_attrs')
    create_sp.assert_called_once_with(
        context.zipkin_attrs, 'foo', ann.return_value,
        binary_ann.return_value, False)
    b64.assert_called_once_with(create_sp.return_value)


@mock.patch('pyramid_zipkin.logging_helper.zipkin_logger', autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.time.time', autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.log_service_span', autospec=True)
def test_zipkin_logging_context_logs_service_span_if_sampled_and_success(
        log_span, time, _, context):
    context.start_timestamp = 24
    context.response_status_code = 200
    context.handler = mock.Mock(spans={})
    time.return_value = 42
    context.zipkin_attrs.is_sampled = True
    context.log_spans()
    log_span.assert_called_once_with(
        context.zipkin_attrs, 24, 42, context.request_path_qs,
        'endpoint_attrs', context.request_method, context.registry_settings)


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
                  'name': 'foo', 'type': 'service'}
    handler = logging_helper.ZipkinLoggerHandler(sampled_zipkin_attr)
    handler.emit(record)
    store_sp.assert_called_once_with('foo', False, 'ann1', 'bann1')


def test_store_span_creates_a_new_entry_to_dict_if_span_name_not_present():
    handler = logging_helper.ZipkinLoggerHandler('foo')
    handler.store_span('a', False, {'foo': 2}, {'bar': 'baz'})
    assert handler.spans == {
        ('a', False): {'annotations': {'foo': 2},
                       'binary_annotations': {'bar': 'baz'},
                       'span_name': 'a',
                       'is_client': False}}


def test_store_span_adds_to_current_entry_if_span_name_already_present():
    handler = logging_helper.ZipkinLoggerHandler('foo')
    handler.spans = {('a', False): {'annotations': {'a': 2},
                                    'binary_annotations': {'asdf': 'qwe'},
                                    'span_name': 'a',
                                    'is_client': False}}
    handler.store_span('a', False, {'foo': 3}, {'bar': 'baz'})
    assert handler.spans == {
        ('a', False): {'annotations': {'a': 2, 'foo': 3},
                       'binary_annotations': {'asdf': 'qwe', 'bar': 'baz'},
                       'span_name': 'a',
                       'is_client': False}}


def test_zipkin_handler_raises_exception_if_ann_and_bann_not_provided(
        sampled_zipkin_attr):
    record = mock.Mock(msg={'name': 'foo'})
    handler = logging_helper.ZipkinLoggerHandler(sampled_zipkin_attr)
    with pytest.raises(ZipkinError) as excinfo:
        handler.emit(record)
    assert ("Atleast one of annotation/binary annotation has to be provided"
            " for foo span" == str(excinfo.value))


@mock.patch('pyramid_zipkin.logging_helper.create_span', autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.base64_thrift', autospec=True)
def test_log_span_calls_scribe_handler_with_correct_params(b64, create_sp):
    scribe_handler = mock.Mock()
    registry = {'zipkin.scribe_handler': scribe_handler,
                'zipkin.scribe_stream_name': 'foo'}
    logging_helper.log_span('attr', 'X', registry, 'ann', 'bann', 'is_client')
    scribe_handler.assert_called_once_with('foo', b64.return_value)


@mock.patch('pyramid_zipkin.logging_helper.create_span', autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.base64_thrift', autospec=True)
def test_log_span_uses_default_stream_name_if_not_provided(b64, create_sp):
    scribe_handler = mock.Mock()
    registry = {'zipkin.scribe_handler': scribe_handler}
    logging_helper.log_span('attr', 'X', registry, 'ann', 'bann', 'is_client')
    scribe_handler.assert_called_once_with('zipkin', b64.return_value)


@mock.patch('pyramid_zipkin.logging_helper.create_span', autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.base64_thrift', autospec=True)
def test_log_span_raises_error_if_handler_not_defined(b64, create_sp):
    registry = {'zipkin.scribe_stream_name': 'foo'}
    with pytest.raises(ZipkinError) as excinfo:
        logging_helper.log_span('attr', 'X', registry, 'ann', 'bann', '_')
    assert ("`zipkin.scribe_handler` is a required config property" in str(
        excinfo.value))
