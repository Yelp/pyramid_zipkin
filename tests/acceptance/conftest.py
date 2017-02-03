import pytest


@pytest.fixture
def default_trace_id_generator(dummy_request):
    return lambda dummy_request: '17133d482ba4f605'


@pytest.fixture
def settings():
    return {
        'zipkin.tracing_percent': 100,
        'zipkin.trace_id_generator': default_trace_id_generator,
    }


@pytest.fixture
def host():
    return {'port': 80, 'service_name': 'acceptance_service'}


@pytest.fixture
def annotation(host):
    return {'host': host}


@pytest.fixture
def uri_binary_annotation(host):
    return {'key': 'http.uri', 'host': host, 'annotation_type': 6}


@pytest.fixture
def uri_qs_binary_annotation(host):
    return {'key': 'http.uri.qs', 'host': host, 'annotation_type': 6}


@pytest.fixture
def response_status_code_annotation(host):
    return {'key': 'response_status_code', 'host': host, 'annotation_type': 6}


@pytest.fixture
def get_span(
    annotation,
    uri_binary_annotation,
    uri_qs_binary_annotation,
    response_status_code_annotation,
):
    sr_annotation = annotation.copy()
    sr_annotation['value'] = 'sr'

    ss_annotation = annotation.copy()
    ss_annotation['value'] = 'ss'

    uri_binary_annotation['value'] = '/sample'
    uri_qs_binary_annotation['value'] = '/sample'

    response_status_code_annotation['value'] = '200'

    return {'debug': False,
            'id': 1,
            'parent_id': None,
            'duration': None,
            'timestamp': None,
            'annotations': sorted(
                [sr_annotation, ss_annotation],
                key=lambda ann: ann['value'],
            ),
            'binary_annotations': [
                uri_binary_annotation,
                uri_qs_binary_annotation,
                response_status_code_annotation,
            ],
            'name': 'GET /sample',
            # An optional field for 128-bit trace IDs that py-zipkin doesn't
            # set. See https://github.com/Yelp/py_zipkin/issues/28
            'trace_id_high': None,
            }
