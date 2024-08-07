from py_zipkin import Encoding
from py_zipkin.zipkin import create_http_headers_for_new_span
from py_zipkin.zipkin import zipkin_span
from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.tweens import EXCVIEW
from pyramid.view import view_config


@view_config(route_name='sample_route', renderer='json')
def sample(dummy_request):
    return {}


@view_config(route_name='sample_route_v2', renderer='json')
def sample_v2(dummy_request):
    with zipkin_span(
        service_name='root_service',
        span_name='v2',
        annotations={'foo': 1664500002.0, 'bar': 1664500001.0},
        binary_annotations={'ping': 'pong'},
    ):
        return {}


@view_config(route_name='sample_route_v2_client', renderer='json')
def sample_v2_client(dummy_request):
    with zipkin_span(
        service_name='foo_service',
        span_name='v2_client',
        annotations={'foo_client': 1664500002.0},
    ):
        pass
    with zipkin_span(
        service_name='bar_service',
        span_name='v2_client',
        annotations={'bar_client': 1664500001.0},
    ):
        pass
    return {}


@view_config(route_name='span_context', renderer='json')
def span_context(dummy_request):
    # Creates a new span, a child of the server span
    with zipkin_span(
        service_name='child',
        span_name='get',
        annotations={'child_annotation': 1664500000.0},
        binary_annotations={'foo': 'bar', 'child': 'true'},
    ):
        with zipkin_span(
            service_name='grandchild',
            span_name='put',
            annotations={'grandchild_annotation': 1664500000.0},
            binary_annotations={'grandchild': 'true'},
        ):
            return {}


@view_config(route_name='decorator_context', renderer='json')
def decorator_context(dummy_request):

    @zipkin_span(
        service_name='my_service',
        span_name='my_span',
        binary_annotations={'a': '1'},
    )
    def some_function(a, b):
        return str(a + b)

    return {'result': some_function(1, 2)}


@view_config(route_name='pattern_route', renderer='json')
def pattern_route(dummy_request):
    return {'result': dummy_request.matchdict['petId']}


@view_config(route_name='sample_route_child_span', renderer='json')
def sample_child_span(dummy_request):
    return create_http_headers_for_new_span()


@view_config(route_name='server_error', renderer='json')
def server_error(dummy_request):
    response = Response('Server Error!')
    response.status_int = 500
    return response


@view_config(route_name='client_error', renderer='json')
def client_error(dummy_request):
    response = Response('Client Error!')
    response.status_int = 400
    return response


@view_config(route_name='redirect', renderer='json')
def redirect(dummy_request):
    response = Response('Redirectional')
    response.status_int = 302
    return response


@view_config(route_name='information_route', renderer='json')
def information_route(dummy_request):
    response = Response('Informational')
    response.status_int = 199
    return response


def main(global_config, **settings):
    """ Very basic pyramid app """
    settings['service_name'] = 'acceptance_service'
    settings['zipkin.transport_handler'] = lambda x, y: None
    settings['zipkin.encoding'] = Encoding.V2_JSON

    config = Configurator(settings=settings)

    config.add_route('sample_route', '/sample')
    config.add_route('sample_route_v2', '/sample_v2')
    config.add_route('sample_route_v2_client', '/sample_v2_client')
    config.add_route('sample_route_child_span', '/sample_child_span')
    config.add_route('span_context', '/span_context')
    config.add_route('decorator_context', '/decorator_context')
    config.add_route('pattern_route', '/pet/{petId}')

    config.add_route('server_error', '/server_error')
    config.add_route('client_error', '/client_error')
    config.add_route('information_route', '/information_route')
    config.add_route('redirect', '/redirect')

    config.scan()

    config.add_tween('pyramid_zipkin.tween.zipkin_tween', over=EXCVIEW)

    return config.make_wsgi_app()
