import mock

from pyramid_zipkin import thrift_helper


@mock.patch('pyramid_zipkin.thrift_helper.generate_span_id', autospec=True)
@mock.patch('pyramid_zipkin.thrift_helper.zipkin_core.Span', autospec=True)
def test_create_span_creates_a_child_span_object_for_child(
        Span, gen_span, sampled_zipkin_attr):
    gen_span.return_value = '56'
    get_id = thrift_helper.get_id
    assert Span.return_value == thrift_helper.create_span(
        sampled_zipkin_attr, 'foo', 'ann', 'binary_ann', is_client=True)
    Span.assert_called_once_with(
        **{'name': 'foo', 'trace_id': 18, 'binary_annotations': 'binary_ann',
           'annotations': 'ann', 'parent_id': get_id('23'),
           'id': get_id('56')})


@mock.patch('pyramid_zipkin.thrift_helper.zipkin_core.Span', autospec=True)
def test_create_span_creates_a_default_span_object(
        Span, sampled_zipkin_attr):
    get_id = thrift_helper.get_id
    assert Span.return_value == thrift_helper.create_span(
        sampled_zipkin_attr, 'foo', 'ann', 'binary_ann')
    Span.assert_called_once_with(
        **{'name': 'foo', 'trace_id': 18, 'binary_annotations': 'binary_ann',
           'annotations': 'ann', 'parent_id': get_id('34'),
           'id': get_id('23')})


def test_create_endpoint_creates_correct_endpoint(request):
    request.registry.settings = {'service_name': 'foo'}
    request.server_port = 8080
    endpoint = thrift_helper.create_endpoint(request)
    assert endpoint.service_name == 'foo'
    assert endpoint.port == 8080


def test_get_id_with_empty_string():
    assert thrift_helper.get_id('') == 0


def test_get_id_with_number():
    assert thrift_helper.get_id('42') == int('42', 16)


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
