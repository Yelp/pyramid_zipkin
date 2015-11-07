import mock

from pyramid_zipkin import thread_local


@mock.patch('pyramid_zipkin.thread_local._thread_local.requests', [])
def test_get_zipkin_attrs_returns_none_if_no_requests():
    assert not thread_local.get_zipkin_attrs()


@mock.patch('pyramid_zipkin.thread_local._thread_local.requests', ['foo'])
def test_get_zipkin_attrs_returns_the_last_of_the_list():
    assert 'foo' == thread_local.get_zipkin_attrs()


@mock.patch('pyramid_zipkin.thread_local._thread_local.requests', [])
def test_pop_zipkin_attrs_does_nothing_if_no_requests():
    assert not thread_local.pop_zipkin_attrs()


@mock.patch('pyramid_zipkin.thread_local._thread_local.requests', ['foo', 'bar'])
def test_pop_zipkin_attrs_removes_the_last_request():
    assert 'bar' == thread_local.pop_zipkin_attrs()
    assert 'foo' == thread_local.get_zipkin_attrs()


@mock.patch('pyramid_zipkin.thread_local._thread_local.requests', ['foo'])
def test_push_zipkin_attrs_adds_new_request_to_list():
    assert 'foo' == thread_local.get_zipkin_attrs()
    thread_local.push_zipkin_attrs('bar')
    assert 'bar' == thread_local.get_zipkin_attrs()
