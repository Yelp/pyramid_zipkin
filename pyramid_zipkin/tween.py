import functools
import warnings
from collections import namedtuple
from typing import Any
from typing import Callable

from py_zipkin import Encoding
from py_zipkin import Kind
from py_zipkin.exception import ZipkinError
from py_zipkin.storage import get_default_tracer
from py_zipkin.transport import BaseTransportHandler
from pyramid.registry import Registry
from pyramid.request import Request
from pyramid.response import Response

from pyramid_zipkin.request_helper import create_zipkin_attr
from pyramid_zipkin.request_helper import get_binary_annotations
from pyramid_zipkin.request_helper import should_not_sample_path
from pyramid_zipkin.request_helper import should_not_sample_route


def _getattr_path(obj: Any, path: str) -> Any:
    """
    getattr for a dot separated path

    If an AttributeError is raised, it will return None.
    """
    if not path:
        return None

    for attr in path.split('.'):
        obj = getattr(obj, attr, None)
    return obj


_ZipkinSettings = namedtuple('_ZipkinSettings', [
    'zipkin_attrs',
    'transport_handler',
    'service_name',
    'span_name',
    'add_logging_annotation',
    'report_root_timestamp',
    'host',
    'port',
    'context_stack',
    'firehose_handler',
    'post_handler_hook',
    'max_span_batch_size',
    'use_pattern_as_span_name',
    'encoding',
])


def _get_settings_from_request(request: Request) -> _ZipkinSettings:
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
    zipkin.firehose_handler: [EXPERIMENTAL] this enables "firehose tracing",
        which will log 100% of the spans to this handler, regardless of
        sampling decision. This is experimental and may change or be removed
        at any time without warning.
    zipkin.use_pattern_as_span_name: if true, we'll use the pyramid route pattern
        as span name. If false (default) we'll keep using the raw url path.
    """
    settings = request.registry.settings

    # Creates zipkin_attrs and attaches a zipkin_trace_id attr to the request
    if 'zipkin.create_zipkin_attr' in settings:
        zipkin_attrs = settings['zipkin.create_zipkin_attr'](request)
    else:
        zipkin_attrs = create_zipkin_attr(request)

    if 'zipkin.transport_handler' in settings:
        transport_handler = settings['zipkin.transport_handler']
        if not isinstance(transport_handler, BaseTransportHandler):
            warnings.warn(
                'Using a function as transport_handler is deprecated. '
                'Please extend py_zipkin.transport.BaseTransportHandler',
                DeprecationWarning,
            )
            stream_name = settings.get('zipkin.stream_name', 'zipkin')
            transport_handler = functools.partial(transport_handler, stream_name)
    else:
        raise ZipkinError(
            "`zipkin.transport_handler` is a required config property, which"
            " is missing. Have a look at py_zipkin's docs for how to implement"
            " it: https://github.com/Yelp/py_zipkin#transport"
        )

    context_stack = _getattr_path(request, settings.get('zipkin.request_context'))

    service_name = settings.get('service_name', 'unknown')
    span_name = f'{request.method} {request.path}'
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
    zipkin_host = settings.get('zipkin.host')
    zipkin_port = settings.get('zipkin.port', request.server_port)
    firehose_handler = settings.get('zipkin.firehose_handler')
    post_handler_hook = settings.get('zipkin.post_handler_hook')
    max_span_batch_size = settings.get('zipkin.max_span_batch_size')
    use_pattern_as_span_name = bool(
        settings.get('zipkin.use_pattern_as_span_name', False),
    )
    encoding = settings.get('zipkin.encoding', Encoding.V2_JSON)
    return _ZipkinSettings(
        zipkin_attrs,
        transport_handler,
        service_name,
        span_name,
        add_logging_annotation,
        report_root_timestamp,
        zipkin_host,
        zipkin_port,
        context_stack,
        firehose_handler,
        post_handler_hook,
        max_span_batch_size,
        use_pattern_as_span_name,
        encoding=encoding,
    )


Handler = Callable[[Request], Response]


def zipkin_tween(handler: Handler, registry: Registry) -> Handler:
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
    def tween(request: Request) -> Response:
        zipkin_settings = _get_settings_from_request(request)
        tracer = get_default_tracer()

        tween_kwargs = dict(
            service_name=zipkin_settings.service_name,
            span_name=zipkin_settings.span_name,
            zipkin_attrs=zipkin_settings.zipkin_attrs,
            transport_handler=zipkin_settings.transport_handler,
            host=zipkin_settings.host,
            port=zipkin_settings.port,
            add_logging_annotation=zipkin_settings.add_logging_annotation,
            report_root_timestamp=zipkin_settings.report_root_timestamp,
            context_stack=zipkin_settings.context_stack,
            max_span_batch_size=zipkin_settings.max_span_batch_size,
            encoding=zipkin_settings.encoding,
            kind=Kind.SERVER,
        )

        # Only set the firehose_handler if it's defined and only if the current
        # request is not blacklisted. This prevents py_zipkin from emitting
        # firehose spans for blacklisted paths like /status
        if zipkin_settings.firehose_handler is not None and \
                not should_not_sample_path(request) and \
                not should_not_sample_route(request):
            tween_kwargs['firehose_handler'] = zipkin_settings.firehose_handler

        with tracer.zipkin_span(**tween_kwargs) as zipkin_context:
            response = None
            try:
                response = handler(request)
            except Exception as e:
                zipkin_context.update_binary_annotations({
                    'error.type': type(e).__name__,
                    'response_status_code': '500'
                })
                raise e
            finally:
                if zipkin_settings.use_pattern_as_span_name \
                        and request.matched_route:
                    zipkin_context.override_span_name('{} {}'.format(
                        request.method,
                        request.matched_route.pattern,
                    ))
                zipkin_context.update_binary_annotations(
                    get_binary_annotations(request, response),
                )

                if zipkin_settings.post_handler_hook:
                    zipkin_settings.post_handler_hook(
                        request,
                        response,
                        zipkin_context
                    )

            return response

    return tween
