import mock
import pytest

from pyramid_zipkin import request_helper


@pytest.fixture
def request():
    request = mock.Mock()
    request.registry.settings = {}
    request.headers = {}
    request.unique_request_id = '42'
    request.path = 'bla'
    return request


@pytest.fixture
def zipkin_attributes():
    return {'trace_id': '12',
            'span_id': '23',
            'parent_span_id': '34',
            'flags': '45',
            }


@pytest.fixture
def sampled_zipkin_attr(zipkin_attributes):
    return request_helper.ZipkinAttrs(is_sampled=True, **zipkin_attributes)


@pytest.fixture
def unsampled_zipkin_attr(zipkin_attributes):
    return request_helper.ZipkinAttrs(is_sampled=False, **zipkin_attributes)
