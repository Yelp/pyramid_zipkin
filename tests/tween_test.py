import collections

import mock
import py_zipkin.storage
import pytest

from pyramid_zipkin import tween
from tests.acceptance.test_helper import MockTransport


DummyRequestContext = collections.namedtuple(
    'RequestContext',
    ['zipkin_context'],
)


@pytest.mark.parametrize('is_tracing', [True, False])
@mock.patch('pyramid_zipkin.tween.zipkin_span', autospec=True)
def test_zipkin_tween_sampling(
    mock_span,
    dummy_request,
    dummy_response,
    is_tracing,
):
    """
    We should enter py_zipkin context manager and
    generate a trace id regardless of whether we are sampling
    """
    dummy_request.registry.settings = {
        'zipkin.is_tracing': lambda _: is_tracing,
        'zipkin.transport_handler': MockTransport(),
    }
    handler = mock.Mock()
    handler.return_value = dummy_response

    assert tween.zipkin_tween(handler, None)(dummy_request) == dummy_response
    assert handler.call_count == 1
    assert mock_span.call_count == 1


@pytest.mark.parametrize(['set_callback', 'called'], [(False, 0), (True, 1)])
@pytest.mark.parametrize('is_tracing', [True, False])
@mock.patch('pyramid_zipkin.tween.zipkin_span', autospec=True)
def test_zipkin_tween_post_handler_hook(
    mock_span,
    dummy_request,
    dummy_response,
    is_tracing,
    set_callback,
    called,
):
    """
    We should invoke the post processor callback regardless of trace id
    or sampling
    """
    mock_post_handler_hook = mock.Mock()

    dummy_request.registry.settings = {
        'zipkin.is_tracing': lambda _: is_tracing,
        'zipkin.transport_handler': MockTransport(),
    }
    if set_callback:
        dummy_request.registry.settings['zipkin.post_handler_hook'] = \
            mock_post_handler_hook

    handler = mock.Mock()
    handler.return_value = dummy_response

    assert tween.zipkin_tween(handler, None)(dummy_request) == dummy_response
    assert handler.call_count == 1
    assert mock_span.call_count == 1
    assert mock_post_handler_hook.call_count == called
    if set_callback:
        mock_post_handler_hook.assert_called_once_with(
            dummy_request,
            dummy_response,
        )


@mock.patch('py_zipkin.storage.ThreadLocalStack', autospec=True)
def test_zipkin_tween_context_stack(
    mock_thread_local_stack,
    dummy_request,
    dummy_response,
):
    dummy_request.registry.settings = {
        'zipkin.is_tracing': lambda _: False,
        'zipkin.transport_handler': MockTransport(),
        'zipkin.request_context': 'rctxstorage.zipkin_context',
    }

    context_stack = mock.Mock(spec=py_zipkin.storage.Stack)
    dummy_request.rctxstorage = DummyRequestContext(
        zipkin_context=context_stack,
    )

    handler = mock.Mock(return_value=dummy_response)
    assert tween.zipkin_tween(handler, None)(dummy_request) == dummy_response

    assert mock_thread_local_stack.call_count == 0
    assert context_stack.push.call_count == 1
    assert context_stack.pop.call_count == 1


@mock.patch('py_zipkin.storage.ThreadLocalStack', autospec=True)
def test_zipkin_tween_context_stack_none(
    mock_thread_local_stack,
    dummy_request,
    dummy_response,
):
    mock_thread_local_stack_instance = mock.Mock()
    mock_thread_local_stack.return_value = mock_thread_local_stack_instance

    dummy_request.registry.settings = {
        'zipkin.is_tracing': lambda _: False,
        'zipkin.transport_handler': MockTransport(),
        'request_context': 'rctxstorage',
    }

    # explicitly delete attribute, will raise AttributeError on access
    delattr(dummy_request, dummy_request.registry.settings['request_context'])

    handler = mock.Mock(return_value=dummy_response)
    assert tween.zipkin_tween(handler, None)(dummy_request) == dummy_response

    assert mock_thread_local_stack.call_count == 1
    assert mock_thread_local_stack_instance.push.call_count == 1
    assert mock_thread_local_stack_instance.pop.call_count == 1


def test_getattr_path():
    request_context = DummyRequestContext(zipkin_context=object())
    assert tween._getattr_path(request_context, 'zipkin_context.__class__')

    # missing attribute
    tween._getattr_path(request_context, 'zipkin_context.missing') is None

    # attribute is None
    mock_object = mock.Mock(nil=None)
    assert tween._getattr_path(mock_object, 'nil') is None


def test_logs_warning_if_using_function_as_transport(
    dummy_request,
    dummy_response,
):
    dummy_request.registry.settings = {
        'zipkin.is_tracing': lambda _: False,
        'zipkin.transport_handler': lambda x: None,
        'request_context': 'rctxstorage',
    }

    handler = mock.Mock(return_value=dummy_response)
    with pytest.deprecated_call():
        tween.zipkin_tween(handler, None)(dummy_request)
