import pytest


@pytest.fixture
def default_trace_id_generator(request):
    return lambda request: '0x42'


@pytest.fixture
def sampled_trace_id_generator(request):
    return lambda request: '0x0'


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
def get_span(annotation, uri_binary_annotation, uri_qs_binary_annotation):
    sr_annotation = annotation.copy()
    sr_annotation['value'] = 'sr'

    ss_annotation = annotation.copy()
    ss_annotation['value'] = 'ss'

    uri_binary_annotation['value'] = '/sample'
    uri_qs_binary_annotation['value'] = '/sample'

    return {'debug': False,
            'id': 1,
            'parent_id': 0,
            'duration': None,
            'timestamp': None,
            'annotations': sorted([sr_annotation, ss_annotation],
                                  key=lambda ann: ann['value']),
            'binary_annotations': [uri_binary_annotation,
                                   uri_qs_binary_annotation],
            'name': 'GET',
            }
