import mock

from pyramid_zipkin import thrift_helper


@mock.patch(
    'pyramid_zipkin.thrift_helper.generate_random_64bit_string',
    autospec=True,
)
@mock.patch('pyramid_zipkin.thrift_helper.zipkin_core.Span', autospec=True)
def test_create_span_creates_a_child_span_object_for_child(
        Span, gen_random_str, sampled_zipkin_attr):
    gen_random_str.return_value = '47133d482ba4f605'
    unsigned_hex_to_signed_int = thrift_helper.unsigned_hex_to_signed_int
    assert Span.return_value == thrift_helper.create_span(
        zipkin_attrs=sampled_zipkin_attr,
        span_name='foo',
        annotations=['annotations'],
        binary_annotations=['binary_annotations'],
        is_client=True,
    )
    Span.assert_called_once_with(**{
        'name': 'foo',
        'trace_id': unsigned_hex_to_signed_int('17133d482ba4f605'),
        'annotations': ['annotations'],
        'binary_annotations': ['binary_annotations'],
        'parent_id': unsigned_hex_to_signed_int('27133d482ba4f605'),
        'id': unsigned_hex_to_signed_int('47133d482ba4f605'),
    })


@mock.patch('pyramid_zipkin.thrift_helper.zipkin_core.Span', autospec=True)
def test_create_span_creates_a_default_span_object(
        Span, sampled_zipkin_attr):
    unsigned_hex_to_signed_int = thrift_helper.unsigned_hex_to_signed_int
    assert Span.return_value == thrift_helper.create_span(
        zipkin_attrs=sampled_zipkin_attr,
        span_name='foo',
        annotations=['annotations'],
        binary_annotations=['binary_annotations'],
        is_client=False,
    )
    Span.assert_called_once_with(**{
        'name': 'foo',
        'trace_id': unsigned_hex_to_signed_int('17133d482ba4f605'),
        'binary_annotations': ['binary_annotations'],
        'annotations': ['annotations'],
        'parent_id': unsigned_hex_to_signed_int('37133d482ba4f605'),
        'id': unsigned_hex_to_signed_int('27133d482ba4f605'),
    })


@mock.patch('socket.gethostbyname', autospec=True)
def test_create_endpoint_creates_correct_endpoint(gethostbyname, request):
    gethostbyname.return_value = '0.0.0.0'
    request.registry.settings = {'service_name': 'foo'}
    request.server_port = 8080
    endpoint = thrift_helper.create_endpoint(request)
    assert endpoint.service_name == 'foo'
    assert endpoint.port == 8080
    # An IP address of 0.0.0.0 unpacks to just 0
    assert endpoint.ipv4 == 0


@mock.patch('socket.gethostbyname', autospec=True)
def test_copy_endpoint_with_new_service_name(gethostbyname, request):
    gethostbyname.return_value = '0.0.0.0'
    request.registry.settings = {'service_name': 'foo'}
    request.server_port = 8080
    endpoint = thrift_helper.create_endpoint(request)
    new_endpoint = thrift_helper.copy_endpoint_with_new_service_name(
            endpoint, 'blargh')
    assert new_endpoint.port == 8080
    assert new_endpoint.service_name == 'blargh'
    # An IP address of 0.0.0.0 unpacks to just 0
    assert endpoint.ipv4 == 0


def test_get_id_with_number():
    assert thrift_helper.unsigned_hex_to_signed_int('17133d482ba4f605') == \
        1662740067609015813
    assert thrift_helper.unsigned_hex_to_signed_int('b6dbb1c2b362bf51') == \
        -5270423489115668655


def test_create_annotation():
    ann = thrift_helper.create_annotation('foo', 'bar', 'baz')
    assert ('foo', 'bar', 'baz') == (ann.timestamp, ann.value, ann.host)


@mock.patch('pyramid_zipkin.thrift_helper.create_annotation', autospec=True)
def test_annotation_list_builder(ann_mock):
    ann_list = {'foo': 1, 'bar': 2}
    thrift_helper.annotation_list_builder(ann_list, 'host')
    ann_mock.assert_any_call(1000000, 'foo', 'host')
    ann_mock.assert_any_call(2000000, 'bar', 'host')
    assert ann_mock.call_count == 2


def test_create_binary_annotation():
    bann = thrift_helper.create_binary_annotation(
        'foo', 'bar', 'baz', 'bla')
    assert ('foo', 'bar', 'baz', 'bla') == (
        bann.key, bann.value, bann.annotation_type, bann.host)


@mock.patch('pyramid_zipkin.thrift_helper.create_binary_annotation',
            autospec=True)
def test_binary_annotation_list_builder(bann_mock):
    bann_list = {'key1': 'val1', 'key2': 'val2'}
    thrift_helper.binary_annotation_list_builder(bann_list, 'host')
    bann_mock.assert_any_call('key1', 'val1', 6, 'host')
    bann_mock.assert_any_call('key2', 'val2', 6, 'host')
    assert bann_mock.call_count == 2
