import mock

from pyramid_zipkin import request_helper


@mock.patch('pyramid_zipkin.request_helper.codecs.encode', autospec=True)
def test_generate_random_64bit_string(rand):
    rand.return_value = '42'
    assert request_helper.generate_random_64bit_string() == '42'


@mock.patch('pyramid_zipkin.request_helper.generate_random_64bit_string',
            autospec=True)
def test_generate_span_id(rand):
    rand.return_value = '42'
    assert request_helper.generate_span_id() == '0x42'


def test_should_not_sample_path_returns_true_if_path_is_blacklisted(request):
    request.registry.settings = {'zipkin.blacklisted_paths': [r'^/foo/?']}
    for path in ['/foo', '/foo/1/3', '/foo/bar', '/foobar']:
        request.path = path
        assert request_helper.should_not_sample_path(request)


def test_should_not_sample_path_returns_false_if_path_not_blacklisted(request):
    request.registry.settings = {'zipkin.blacklisted_paths': [r'^/foo/?']}
    for path in ['/bar', '/bar/foo', '/foe']:
        request.path = path
        assert not request_helper.should_not_sample_path(request)


def test_should_not_sample_route_returns_true_if_route_is_blacklisted(request):
    request.registry.settings = {'zipkin.blacklisted_routes': ['foo.bar']}
    route = mock.Mock()
    route.name = 'foo.bar'
    request.registry.queryUtility = lambda _: lambda req: {'route': route}
    assert request_helper.should_not_sample_route(request)


def test_should_not_sample_route_returns_false_if_route_is_not_blacklisted(
        request):
    request.registry.settings = {'zipkin.blacklisted_routes': ['bar']}
    route = mock.Mock()
    route.name = 'foo'
    request.registry.queryUtility = lambda _: lambda req: {'route': route}
    assert not request_helper.should_not_sample_route(request)


def test_should_not_sample_route_returns_false_if_blacklisted_list_is_empty(
        request):
    assert not request_helper.should_not_sample_route(request)


def test_should_be_sampled_as_per_zipkin_tracing_percent_retrns_true_for_100():
    assert request_helper.should_sample_as_per_zipkin_tracing_percent(
        100.0, '42')


def test_should_be_sampled_as_per_zipkin_tracing_percent_returns_false_for_0():
    assert not request_helper.should_sample_as_per_zipkin_tracing_percent(
        0, '42')


@mock.patch('pyramid_zipkin.request_helper.should_not_sample_path',
            autospec=True)
def test_is_tracing_returns_false_if_path_should_not_be_sampled(mock, request):
    mock.return_value = True
    assert not request_helper.is_tracing(request)


@mock.patch('pyramid_zipkin.request_helper.should_not_sample_route',
            autospec=True)
def test_is_tracing_return_false_if_route_should_not_be_sampled(mock, request):
    mock.return_value = True
    assert not request_helper.is_tracing(request)


def test_is_tracing_returns_true_if_sampled_value_in_header_was_true(request):
    request.headers = {'X-B3-Sampled': '1'}
    assert request_helper.is_tracing(request)


def test_is_tracing_returns_false_if_sampled_value_in_header_was_false(request):
    request.headers = {'X-B3-Sampled': '0'}
    assert not request_helper.is_tracing(request)


@mock.patch(
    'pyramid_zipkin.request_helper.should_sample_as_per_zipkin_tracing_percent',
    autospec=True)
def test_is_tracing_returns_what_tracing_percent_method_returns_for_rest(
        mock, request):
    request.zipkin_trace_id = '42'
    assert mock.return_value == request_helper.is_tracing(request)
    mock.assert_called_once_with(
        request_helper.DEFAULT_REQUEST_TRACING_PERCENT, '42')


@mock.patch(
    'pyramid_zipkin.request_helper.should_sample_as_per_zipkin_tracing_percent',
    autospec=True)
def test_is_tracing_returns_false_if_override_does_not_exist(mock, request):
    mock.return_value = False
    request.registry.settings = {}
    assert not request_helper.is_tracing(request)


@mock.patch(
    'pyramid_zipkin.request_helper.should_sample_as_per_zipkin_tracing_percent',
    autospec=True)
def test_is_tracing_returns_false_if_override_returns_false(mock, request):
    mock.return_value = False
    request.registry.settings = {
        'zipkin.tracing_override': lambda request: False,
    }
    assert not request_helper.is_tracing(request)


def test_is_tracing_returns_true_if_override_returns_true(request):
    request.registry.settings = {
        'zipkin.tracing_override': lambda request: True,
    }
    assert request_helper.is_tracing(request)


def test_get_trace_id_returns_header_value_if_present(request):
    request.headers = {'X-B3-TraceId': 'foo'}
    request.registry.setttings = {'zipkin.trace_id_generator': lambda r: 'foo'}
    assert 'foo' == request_helper.get_trace_id(request)


def test_get_trace_id_runs_custom_trace_id_generator_if_present(request):
    request.registry.settings = {'zipkin.trace_id_generator': lambda r: 'foo'}
    assert 'foo' == request_helper.get_trace_id(request)


@mock.patch('pyramid_zipkin.request_helper.thrift_compatible_string',
            autospec=True)
def test_get_trace_id_returns_some_random_id_by_default(compat, request):
    compat.return_value = 'foo'
    assert 'foo' == request_helper.get_trace_id(request)


@mock.patch('pyramid_zipkin.request_helper.is_tracing', autospec=True)
def test_create_sampled_zipkin_attr_creates_ZipkinAttr_object(mock, request):
    mock.return_value = 'bla'
    request.zipkin_trace_id = '12'
    request.headers = {
        'X-B3-TraceId': '12',
        'X-B3-SpanId': '23',
        'X-B3-ParentSpanId': '34',
        'X-B3-Flags': '45',
        }
    zipkin_attr = request_helper.ZipkinAttrs(
        trace_id='12', span_id='23', parent_span_id='34', flags='45',
        is_sampled='bla')
    assert zipkin_attr == request_helper.create_zipkin_attr(request)
