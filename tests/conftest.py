from unittest import mock

import pytest
from pyramid.request import Request

from pyramid_zipkin import request_helper


@pytest.fixture
def dummy_request():
    request = mock.Mock()
    request.registry.settings = {}
    request.headers = {}
    request.unique_request_id = '17133d482ba4f605'
    request.path = 'bla'
    return request


@pytest.fixture
def get_request():
    request = Request.blank('GET /sample')
    request.registry = mock.Mock()
    request.registry.settings = {}
    request.headers = {}
    request.unique_request_id = '17133d482ba4f605'
    return request


@pytest.fixture
def dummy_response():
    response = mock.Mock()
    response.status_code = 200
    return response


@pytest.fixture
def zipkin_attributes():
    return {'trace_id': '17133d482ba4f605',
            'span_id': '27133d482ba4f605',
            'parent_span_id': '37133d482ba4f605',
            'flags': '45',
            }


@pytest.fixture
def sampled_zipkin_attr(zipkin_attributes):
    return request_helper.ZipkinAttrs(is_sampled=True, **zipkin_attributes)


@pytest.fixture
def unsampled_zipkin_attr(zipkin_attributes):
    return request_helper.ZipkinAttrs(is_sampled=False, **zipkin_attributes)
