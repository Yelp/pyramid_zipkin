import mock

from pyramid_zipkin import tween


@mock.patch('pyramid_zipkin.tween.zipkin_span', autospec=True)
def test_zipkin_tween_not_sampled(mock_span, dummy_request, dummy_response):
    """
    If the request is not sampled, we shouldn't use the
    py_zipkin context manager
    """
    dummy_request.registry.settings = {
        'zipkin.is_tracing': lambda _: False,
        'zipkin.transport_handler': lambda _: None,
    }
    handler = mock.Mock()
    handler.return_value = dummy_response

    assert tween.zipkin_tween(handler, None)(dummy_request) == dummy_response
    assert handler.call_count == 1
    assert mock_span.call_count == 0


@mock.patch('pyramid_zipkin.tween.zipkin_span', autospec=True)
def test_zipkin_tween_sampled(mock_span, dummy_request, dummy_response):
    """
    If the request is sampled, we should wrap the handler in the
    py_zipkin context manager
    """
    dummy_request.registry.settings = {
        'zipkin.is_tracing': lambda _: True,
        'zipkin.transport_handler': lambda _: None,
    }
    handler = mock.Mock()
    handler.return_value = dummy_response

    assert tween.zipkin_tween(handler, None)(dummy_request) == dummy_response
    assert handler.call_count == 1
    assert mock_span.call_count == 1
