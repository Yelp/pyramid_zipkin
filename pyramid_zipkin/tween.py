# -*- coding: utf-8 -*-
import functools
from collections import namedtuple

from py_zipkin.exception import ZipkinError
from py_zipkin.zipkin import zipkin_span

from pyramid_zipkin.request_helper import create_zipkin_attr
from pyramid_zipkin.request_helper import get_binary_annotations


ZipkinSettings = namedtuple('ZipkinSettings', [
    'zipkin_attrs',
    'transport_handler',
    'service_name',
    'span_name',
    'add_logging_annotation',
    'report_root_timestamp',
])


def _get_settings_from_request(request):
    """Extracts Zipkin attributes and configuration from request attributes.
    See the `zipkin_span` context in py-zipkin for more detaied information on
    all the settings.

    Here are the supported Pyramid registry settings:

    zipkin.create_zipkin_attr: allows the service to override the creation of
        Zipkin attributes. For example, if you want to deterministically
        calculate trace ID from some service-specific attributes.
    zipkin.transport_handler: how py-zipkin will log the spans it generates.
    zipkin.stream_name: an additional parameter to be used as the first arg
        to the transport_handler function. A good example is a Kafka topic.
    zipkin.add_logging_annotation: if true, the outermost span in this service
        will have an annotation set when py-zipkin begins its logging.
    zipkin.report_root_timestamp: if true, the outermost span in this service
        will set its timestamp and duration attributes. Use this only if this
        service is not going to have a corresponding client span. See
        https://github.com/Yelp/pyramid_zipkin/issues/68
    """
    settings = request.registry.settings

    # Creates zipkin_attrs and attaches a zipkin_trace_id attr to the request
    if 'zipkin.create_zipkin_attr' in settings:
        zipkin_attrs = settings['zipkin.create_zipkin_attr'](request)
    else:
        zipkin_attrs = create_zipkin_attr(request)

    if 'zipkin.transport_handler' in settings:
        transport_handler = settings['zipkin.transport_handler']
        stream_name = settings.get('zipkin.stream_name', 'zipkin')
        transport_handler = functools.partial(transport_handler, stream_name)
    else:
        raise ZipkinError(
            "`zipkin.transport_handler` is a required config property, which"
            " is missing. It is a callback method which takes a log stream"
            " and a message as params and logs the message via scribe/kafka."
        )

    service_name = settings.get('service_name', 'unknown')
    span_name = '{0} {1}'.format(request.method, request.path)
    add_logging_annotation = settings.get(
        'zipkin.add_logging_annotation',
        False,
    )
    # If the incoming request doesn't have Zipkin headers, this request is
    # assumed to be the root span of a trace. There's also a configuration
    # override to allow services to write their own logic for reporting
    # timestamp/duration.
    if 'zipkin.report_root_timestamp' in settings:
        report_root_timestamp = settings['zipkin.report_root_timestamp']
    else:
        report_root_timestamp = 'X-B3-TraceId' not in request.headers
    return ZipkinSettings(
        zipkin_attrs,
        transport_handler,
        service_name,
        span_name,
        add_logging_annotation,
        report_root_timestamp,
    )


def zipkin_tween(handler, registry):
    """
    Factory for pyramid tween to handle zipkin server logging. Note that even
    if the request isn't sampled, Zipkin attributes are generated and pushed
    into threadlocal storage, so `create_http_headers_for_new_span` and
    `zipkin_span` will have access to the proper Zipkin state.

    Consumes custom create_zipkin_attr function if one is set in the pyramid
    registry.

    :param handler: pyramid request handler
    :param registry: pyramid app registry

    :returns: pyramid tween
    """
    def tween(request):
        zipkin_settings = _get_settings_from_request(request)

        with zipkin_span(
            service_name=zipkin_settings.service_name,
            span_name=zipkin_settings.span_name,
            zipkin_attrs=zipkin_settings.zipkin_attrs,
            transport_handler=zipkin_settings.transport_handler,
            port=request.server_port,
            add_logging_annotation=zipkin_settings.add_logging_annotation,
            report_root_timestamp=zipkin_settings.report_root_timestamp,
        ) as zipkin_context:
            response = handler(request)
            zipkin_context.update_binary_annotations_for_root_span(
                get_binary_annotations(request, response),
            )
            return response

    return tween
