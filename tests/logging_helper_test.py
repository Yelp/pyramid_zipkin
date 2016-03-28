import mock

import pytest

from pyramid_zipkin import logging_helper
from pyramid_zipkin.exception import ZipkinError
from pyramid_zipkin.request_helper import ZipkinAttrs


@pytest.fixture
def context():
    attr = ZipkinAttrs(None, None, None, None, False)
    handler = logging_helper.ZipkinLoggerHandler(attr)
    request = mock.Mock()
    return logging_helper.ZipkinLoggingContext(
        attr, 'thrift_endpoint', handler, request)


@mock.patch('pyramid_zipkin.logging_helper.zipkin_logger', autospec=True)
@mock.patch('pyramid_zipkin.thread_local._thread_local',
            autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.time.time', autospec=True)
def test_zipkin_logging_context(
        time_mock, tl_mock, mock_logger, context):
    # Tests the context manager aspects of the ZipkinLoggingContext
    time_mock.return_value = 42
    tl_mock.requests = []
    # Ignore the actual logging part
    with mock.patch.object(context, 'log_spans'):
        with context:
            mock_logger.addHandler.assert_called_once_with(context.handler)
            assert context.start_timestamp == 42
            assert tl_mock.requests[0] == context.zipkin_attrs
        # Make sure the handler and the zipkin attrs are gone
        mock_logger.removeHandler.assert_called_once_with(context.handler)
        assert tl_mock.requests == []
        assert context.log_spans.call_count == 1


@mock.patch('pyramid_zipkin.logging_helper.time.time', autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.log_span', autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.annotation_list_builder',
            autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.binary_annotation_list_builder',
            autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.copy_endpoint_with_new_service_name',
            autospec=True)
def test_zipkin_logging_context_log_spans(
    copy_endpoint_mock, bin_ann_list_builder, ann_list_builder,
    log_span_mock, time_mock
):
    # This lengthy function tests that the logging context properly
    # logs both client and server spans, while attaching extra annotations
    # logged throughout the context of the trace.
    trace_id = '000000000000000f'
    parent_span_id = '0000000000000001'
    server_span_id = '0000000000000002'
    client_span_id = '0000000000000003'
    client_span_name = 'breadcrumbs'
    client_svc_name = 'svc'
    attr = ZipkinAttrs(
        trace_id=trace_id,
        span_id=server_span_id,
        parent_span_id=parent_span_id,
        flags=None,
        is_sampled=True,
    )
    handler = logging_helper.ZipkinLoggerHandler(attr)
    extra_server_annotations = {
        'parent_span_id': None,
        'annotations': {'foo': 1},
        'binary_annotations': {'what': 'whoa'},
    }
    extra_client_annotations = {
        'parent_span_id': client_span_id,
        'annotations': {'ann1': 1},
        'binary_annotations': {'bann1': 'aww'},
    }
    handler.extra_annotations = [
        extra_server_annotations,
        extra_client_annotations,
    ]
    handler.client_spans = [{
        'span_id': client_span_id,
        'parent_span_id': None,
        'span_name': client_span_name,
        'service_name': client_svc_name,
        'annotations': {'ann2': 2},
        'binary_annotations': {'bann2': 'yiss'},
    }]
    request = mock.Mock()
    # Each of the thrift annotation helpers just reflects its first arg
    # so the annotation dicts can be checked.
    ann_list_builder.side_effect = lambda x, y: x
    bin_ann_list_builder.side_effect = lambda x, y: x

    context = logging_helper.ZipkinLoggingContext(
        attr, 'thrift_endpoint', handler, request)

    context.start_timestamp = 24
    context.response_status_code = 200

    context.binary_annotations_dict = {'k': 'v'}
    time_mock.return_value = 42

    expected_server_annotations = {'foo': 1, 'sr': 24, 'ss': 42}
    expected_server_bin_annotations = {'k': 'v', 'what': 'whoa'}

    expected_client_annotations = {'ann1': 1, 'ann2': 2}
    expected_client_bin_annotations = {'bann1': 'aww', 'bann2': 'yiss'}

    context.log_spans()
    client_log_call, server_log_call = log_span_mock.call_args_list
    assert server_log_call[1] == {
        'span_id': server_span_id,
        'parent_span_id': parent_span_id,
        'trace_id': trace_id,
        'span_name': context.request_method,
        'annotations': expected_server_annotations,
        'binary_annotations': expected_server_bin_annotations,
        'registry_settings': context.registry_settings,
    }
    assert client_log_call[1] == {
        'span_id': client_span_id,
        'parent_span_id': server_span_id,
        'trace_id': trace_id,
        'span_name': client_span_name,
        'annotations': expected_client_annotations,
        'binary_annotations': expected_client_bin_annotations,
        'registry_settings': context.registry_settings,
    }


def test_zipkin_handler_init():
    handler = logging_helper.ZipkinLoggerHandler('foo')
    assert handler.zipkin_attrs == 'foo'


def test_zipkin_handler_does_not_emit_unsampled_record(unsampled_zipkin_attr):
    handler = logging_helper.ZipkinLoggerHandler(unsampled_zipkin_attr)
    assert not handler.emit('bla')


def test_handler_stores_client_span_on_emit(sampled_zipkin_attr):
    record = mock.Mock()
    record.msg = {
        'annotations': 'ann1', 'binary_annotations': 'bann1',
        'name': 'foo', 'service_name': 'blargh',
    }
    handler = logging_helper.ZipkinLoggerHandler(sampled_zipkin_attr)
    assert handler.client_spans == []
    handler.emit(record)
    assert handler.client_spans == [{
        'span_name': 'foo',
        'service_name': 'blargh',
        'parent_span_id': None,
        'span_id': None,
        'annotations': 'ann1',
        'binary_annotations': 'bann1',
    }]


def test_handler_stores_extra_annotations_on_emit(sampled_zipkin_attr):
    record = mock.Mock()
    record.msg = {'annotations': 'ann1', 'binary_annotations': 'bann1'}
    handler = logging_helper.ZipkinLoggerHandler(sampled_zipkin_attr)
    assert handler.extra_annotations == []
    handler.emit(record)
    assert handler.extra_annotations == [{
        'annotations': 'ann1',
        'binary_annotations': 'bann1',
        'parent_span_id': None,
    }]


def test_zipkin_handler_raises_exception_if_ann_and_bann_not_provided(
        sampled_zipkin_attr):
    record = mock.Mock(msg={'name': 'foo'})
    handler = logging_helper.ZipkinLoggerHandler(sampled_zipkin_attr)
    with pytest.raises(ZipkinError) as excinfo:
        handler.emit(record)
    assert ("Atleast one of annotation/binary annotation has to be provided"
            " for foo span" == str(excinfo.value))


@mock.patch('pyramid_zipkin.logging_helper.thrift_obj_in_bytes', autospec=True)
def test_log_span(thrift_obj):
    # Not much logic here, so this is basically a smoke test
    thrift_obj.return_value = 'obj'
    registry = {'zipkin.transport_handler': (lambda x, y: (x, y))}
    stream, span_bytes = logging_helper.log_span(
        span_id='0000000000000002',
        parent_span_id='0000000000000001',
        trace_id='000000000000000f',
        span_name='span',
        annotations='ann',
        binary_annotations='binary_ann',
        registry_settings=registry,
    )
    assert thrift_obj.call_count == 1
    assert stream == 'zipkin'
    assert span_bytes == 'obj'


@mock.patch('pyramid_zipkin.logging_helper.create_span', autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.thrift_obj_in_bytes', autospec=True)
def test_log_span_calls_transport_handler_with_correct_params(thrift_obj,
                                                              create_sp):
    transport_handler = mock.Mock()
    registry = {'zipkin.transport_handler': transport_handler,
                'zipkin.stream_name': 'foo'}
    logging_helper.log_span(
        '0000000000000002', '0000000000000001', '00000000000000015',
        'span', 'ann', 'binary_ann', registry
    )
    transport_handler.assert_called_once_with('foo', thrift_obj.return_value)


@mock.patch('pyramid_zipkin.logging_helper.create_span', autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.thrift_obj_in_bytes', autospec=True)
def test_log_span_uses_default_stream_name_if_not_provided(thrift_obj, create_sp):
    transport_handler = mock.Mock()
    registry = {'zipkin.transport_handler': transport_handler}
    logging_helper.log_span(
        '0000000000000002', '0000000000000001', '00000000000000015',
        'span', 'ann', 'binary_ann', registry
    )
    transport_handler.assert_called_once_with('zipkin', thrift_obj.return_value)


@mock.patch('pyramid_zipkin.logging_helper.create_span', autospec=True)
@mock.patch('pyramid_zipkin.logging_helper.thrift_obj_in_bytes', autospec=True)
def test_log_span_raises_error_if_handler_not_defined(thrift_obj, create_sp):
    with pytest.raises(ZipkinError) as excinfo:
        logging_helper.log_span(
            '0000000000000002', '0000000000000001', '00000000000000015',
            'span', 'ann', 'binary_ann', {}
        )
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
