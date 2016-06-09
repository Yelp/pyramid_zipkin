# -*- coding: utf-8 -*-
import logging

from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config
from pyramid.tweens import MAIN

from pyramid_zipkin import zipkin

zipkin_logger = logging.getLogger('pyramid_zipkin.logger')


@view_config(route_name='sample_route', renderer='json')
def sample(dummy_request):
    return {}


@view_config(route_name='sample_route_v2', renderer='json')
def sample_v2(dummy_request):
    zipkin_logger.debug({
        'annotations': {'foo': 2},
        'binary_annotations': {'ping': 'pong'},
        'name': 'v2',
    })
    zipkin_logger.debug({'annotations': {'bar': 1}, 'name': 'v2'})
    return {}


@view_config(route_name='sample_route_v2_client', renderer='json')
def sample_v2_client(dummy_request):
    zipkin_logger.debug({
        'annotations': {'foo_client': 2},
        'name': 'v2_client',
        'service_name': 'foo_service',
    })
    zipkin_logger.debug({
        'annotations': {'bar_client': 1},
        'name': 'v2_client',
        'service_name': 'bar_service',
    })
    return {}


@view_config(route_name='span_context', renderer='json')
def span_context(dummy_request):
    # These annotations should go to the server span
    zipkin_logger.debug({
        'annotations': {'server_annotation': 1},
        'binary_annotations': {'server': 'true'},
    })
    # Creates a new span, a child of the server span
    with zipkin.SpanContext(
        service_name='child', span_name='get',
        binary_annotations={'foo': 'bar'},
    ):
        # These annotations go to the child span
        zipkin_logger.debug({
            'annotations': {'child_annotation': 1},
            'binary_annotations': {'child': 'true'},
        })
        # This should log a new span with `child` as its parent
        zipkin_logger.debug({
            'annotations': {'grandchild_annotation': 1},
            'binary_annotations': {'grandchild': 'true'},
            'service_name': 'grandchild',
            'name': 'put',
        })
    return {}


@view_config(route_name='sample_route_child_span', renderer='json')
def sample_child_span(dummy_request):
    return zipkin.create_headers_for_new_span()


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


def main(global_config, **settings):
    """ Very basic pyramid app """
    settings['service_name'] = 'acceptance_service'
    settings['zipkin.transport_handler'] = lambda x, y: None

    config = Configurator(settings=settings)

    config.add_route('sample_route', '/sample')
    config.add_route('sample_route_v2', '/sample_v2')
    config.add_route('sample_route_v2_client', '/sample_v2_client')
    config.add_route('sample_route_child_span', '/sample_child_span')
    config.add_route('span_context', '/span_context')

    config.add_route('server_error', '/server_error')
    config.add_route('client_error', '/client_error')

    config.scan()

    config.add_tween('pyramid_zipkin.zipkin.zipkin_tween', over=MAIN)

    return config.make_wsgi_app()
