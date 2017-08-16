import mock

from pyramid_zipkin import tween
import pytest


@pytest.mark.parametrize('is_tracing', [True, False])
@mock.patch('pyramid_zipkin.tween.zipkin_span', autospec=True)
def test_zipkin_tween_sampling(
    mock_span,
    dummy_request,
    dummy_response,
    is_tracing
):
    """
    We should enter py_zipkin context manager and
    generate a trace id regardless of whether we are sampling
    """
    dummy_request.registry.settings = {
        'zipkin.is_tracing': lambda _: is_tracing,
        'zipkin.transport_handler': lambda _: None,
    }
    handler = mock.Mock()
    handler.return_value = dummy_response

    assert tween.zipkin_tween(handler, None)(dummy_request) == dummy_response
    assert handler.call_count == 1
    assert mock_span.call_count == 1
