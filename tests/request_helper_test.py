import mock

from pyramid_zipkin import request_helper


def test_should_not_sample_path_returns_true_if_path_is_blacklisted(
    dummy_request
):
    dummy_request.registry.settings = {'zipkin.blacklisted_paths': [r'^/foo/?']}
    for path in ['/foo', '/foo/1/3', '/foo/bar', '/foobar']:
        dummy_request.path = path
        assert request_helper.should_not_sample_path(dummy_request)


def test_should_not_sample_path_returns_false_if_path_not_blacklisted(
    dummy_request
):
    dummy_request.registry.settings = {'zipkin.blacklisted_paths': [r'^/foo/?']}
    for path in ['/bar', '/bar/foo', '/foe']:
        dummy_request.path = path
        assert not request_helper.should_not_sample_path(dummy_request)


def test_should_not_sample_route_returns_true_if_route_is_blacklisted(
    dummy_request
):
    dummy_request.registry.settings = {'zipkin.blacklisted_routes': ['foo.bar']}
    route = mock.Mock()
    route.name = 'foo.bar'
    dummy_request.registry.queryUtility = lambda _: lambda req: {'route': route}
    assert request_helper.should_not_sample_route(dummy_request)


def test_should_not_sample_route_returns_false_if_route_is_not_blacklisted(
    dummy_request
):
    dummy_request.registry.settings = {'zipkin.blacklisted_routes': ['bar']}
    route = mock.Mock()
    route.name = 'foo'
    dummy_request.registry.queryUtility = lambda _: lambda req: {'route': route}
    assert not request_helper.should_not_sample_route(dummy_request)


def test_should_not_sample_route_returns_false_if_blacklisted_list_is_empty(
    dummy_request
):
    assert not request_helper.should_not_sample_route(dummy_request)


def test_should_be_sampled_as_per_zipkin_tracing_percent_retrns_true_for_100():
    assert request_helper.should_sample_as_per_zipkin_tracing_percent(100.0)


def test_should_be_sampled_as_per_zipkin_tracing_percent_returns_false_for_0():
    assert not request_helper.should_sample_as_per_zipkin_tracing_percent(0)


@mock.patch('pyramid_zipkin.request_helper.should_not_sample_path', autospec=True)
def test_is_tracing_returns_false_if_path_should_not_be_sampled(
    mock, dummy_request
):
    mock.return_value = True
    assert not request_helper.is_tracing(dummy_request)


@mock.patch(
    'pyramid_zipkin.request_helper.should_not_sample_route',
    autospec=True
)
def test_is_tracing_return_false_if_route_should_not_be_sampled(
    mock, dummy_request
):
    mock.return_value = True
    assert not request_helper.is_tracing(dummy_request)


def test_is_tracing_returns_true_if_sampled_value_in_header_was_true(
    dummy_request
):
    dummy_request.headers = {'X-B3-Sampled': '1'}
    assert request_helper.is_tracing(dummy_request)


def test_is_tracing_returns_false_if_sampled_value_in_header_was_fals(
    dummy_request
):
    dummy_request.headers = {'X-B3-Sampled': '0'}
    assert not request_helper.is_tracing(dummy_request)


@mock.patch(
    'pyramid_zipkin.request_helper.should_sample_as_per_zipkin_tracing_percent',
    autospec=True
)
def test_is_tracing_returns_what_tracing_percent_method_returns_for_rest(
    mock, dummy_request
):
    dummy_request.zipkin_trace_id = '42'
    assert mock.return_value == request_helper.is_tracing(dummy_request)
    mock.assert_called_once_with(
        request_helper.DEFAULT_REQUEST_TRACING_PERCENT
    )


def test_get_trace_id_returns_header_value_if_present(dummy_request):
    dummy_request.headers = {'X-B3-TraceId': '48485a3953bb6124'}
    dummy_request.registry.settings = {
        'zipkin.trace_id_generator': lambda r: '17133d482ba4f605',
    }
    assert '48485a3953bb6124' == request_helper.get_trace_id(dummy_request)


def test_get_trace_id_returns_header_value_if_present_128_bit(dummy_request):
    # When someone passes a 128-bit trace id, it ends up as 32 hex characters.
    # We choose the right-most 16 characters (corresponding to the lowest 64 bits)
    dummy_request.headers = {'X-B3-TraceId': '463ac35c9f6413ad48485a3953bb6124'}
    dummy_request.registry.settings = {
        'zipkin.trace_id_generator': lambda r: '17133d482ba4f605',
    }
    assert '48485a3953bb6124' == request_helper.get_trace_id(dummy_request)


def test_create_zipkin_attr_runs_custom_is_tracing_if_present(dummy_request):
    is_tracing = mock.Mock(return_value=True)
    dummy_request.registry.settings = {
        'zipkin.is_tracing': is_tracing,
    }
    request_helper.create_zipkin_attr(dummy_request)
    is_tracing.assert_called_once_with(dummy_request)


def test_get_trace_id_runs_custom_trace_id_generator_if_present(dummy_request):
    dummy_request.registry.settings = {
        'zipkin.trace_id_generator': lambda r: '27133d482ba4f605',
    }
    assert '27133d482ba4f605' == request_helper.get_trace_id(dummy_request)


@mock.patch(
    'pyramid_zipkin.request_helper.generate_random_64bit_string',
    autospec=True
)
def test_get_trace_id_returns_some_random_id_by_default(compat, dummy_request):
    compat.return_value = '37133d482ba4f605'
    assert '37133d482ba4f605' == request_helper.get_trace_id(dummy_request)


@mock.patch('pyramid_zipkin.request_helper.is_tracing', autospec=True)
def test_create_sampled_zipkin_attr_creates_ZipkinAttr_object(
    mock, dummy_request
):
    mock.return_value = 'bla'
    dummy_request.zipkin_trace_id = '12'
    dummy_request.headers = {
        'X-B3-TraceId': '12',
        'X-B3-SpanId': '23',
        'X-B3-ParentSpanId': '34',
        'X-B3-Flags': '45',
    }
    zipkin_attr = request_helper.ZipkinAttrs(
        trace_id='0000000000000012',
        span_id='23',
        parent_span_id='34',
        flags='45',
        is_sampled='bla'
    )
    assert zipkin_attr == request_helper.create_zipkin_attr(dummy_request)


def test_get_trace_id_works_with_old_style_hex_string(dummy_request):
    dummy_request.headers = {'X-B3-TraceId': '-0x3ab5151d76fb85e1'}
    assert 'c54aeae289047a1f' == request_helper.get_trace_id(dummy_request)


def test_convert_signed_hex():
    assert (
        request_helper._convert_signed_hex('0xd68adf75f4cfd13') ==
        '0d68adf75f4cfd13'
    )
    assert (
        request_helper._convert_signed_hex('-0x3ab5151d76fb85e1') ==
        'c54aeae289047a1f'
    )
