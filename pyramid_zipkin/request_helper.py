import random
import re
from typing import Dict
from typing import Optional

from py_zipkin.util import generate_random_128bit_string
from py_zipkin.util import generate_random_64bit_string
from py_zipkin.zipkin import ZipkinAttrs
from pyramid.interfaces import IRoutesMapper
from pyramid.request import Request
from pyramid.response import Response

from pyramid_zipkin.version import __version__


DEFAULT_REQUEST_TRACING_PERCENT = 0.5


def get_trace_id(request: Request) -> str:
    """Gets the trace id based on a request. If not present with the request, a
    completely random 128-bit trace id is generated.

    :param: current active pyramid request
    :returns: the value of the 'X-B3-TraceId' header or a 128-bit hex string
    """
    return request.headers.get('X-B3-TraceId', generate_random_128bit_string())


def should_not_sample_path(request: Request) -> bool:
    """Decided whether current request path should be sampled or not. This is
    checked previous to `should_not_sample_route` and takes precedence.

    :param: current active pyramid request
    :returns: boolean whether current request path is blacklisted.
    """
    blacklisted_paths = request.registry.settings.get(
        'zipkin.blacklisted_paths', [])
    # Only compile strings, since even recompiling existing
    # compiled regexes takes time.
    regexes = [
        re.compile(r) if isinstance(r, str) else r
        for r in blacklisted_paths
    ]
    return any(r.match(request.path) for r in regexes)


def should_not_sample_route(request: Request) -> bool:
    """Decided whether current request route should be sampled or not.

    :param: current active pyramid request
    :returns: boolean whether current request route is blacklisted.
    """
    blacklisted_routes = request.registry.settings.get(
        'zipkin.blacklisted_routes', [])

    if not blacklisted_routes:
        return False
    route_mapper = request.registry.queryUtility(IRoutesMapper)
    route_info = route_mapper(request).get('route')
    return (route_info and route_info.name in blacklisted_routes)


def should_sample_as_per_zipkin_tracing_percent(tracing_percent: float) -> bool:
    """Calculate whether the request should be traced as per tracing percent.

    :param tracing_percent: value between 0.0 to 100.0
    :type tracing_percent: float
    :returns: boolean whether current request should be sampled.
    """
    return (random.random() * 100) < tracing_percent


def is_tracing(request: Request) -> bool:
    """Determine if zipkin should be tracing
    1) Check whether the current request path is blacklisted.
    2) If not, check whether the current request route is blacklisted.
    3) If not, check if specific sampled header is present in the request.
    4) If not, Use a tracing percent (default: 0.5%) to decide.

    :param request: pyramid request object

    :returns: boolean True if zipkin should be tracing
    """
    if should_not_sample_path(request):
        return False
    elif should_not_sample_route(request):
        return False
    elif 'X-B3-Sampled' in request.headers:
        return request.headers.get('X-B3-Sampled') == '1'
    else:
        zipkin_tracing_percent = request.registry.settings.get(
            'zipkin.tracing_percent', DEFAULT_REQUEST_TRACING_PERCENT)
        return should_sample_as_per_zipkin_tracing_percent(
            zipkin_tracing_percent)


def create_zipkin_attr(request: Request) -> ZipkinAttrs:
    """Create ZipkinAttrs object from a request with sampled flag as True.
    Attaches lazy attribute `zipkin_trace_id` with request which is then used
    throughout the tween.

    Consumes custom is_tracing function to determine if the request is traced
    if one is set in the pyramid registry.

    :param request: pyramid request object
    :rtype: :class:`pyramid_zipkin.request_helper.ZipkinAttrs`
    """
    settings = request.registry.settings

    if 'zipkin.is_tracing' in settings:
        is_sampled = settings['zipkin.is_tracing'](request)
    else:
        is_sampled = is_tracing(request)

    span_id = request.headers.get(
        'X-B3-SpanId', generate_random_64bit_string())
    parent_span_id = request.headers.get('X-B3-ParentSpanId', None)
    flags = request.headers.get('X-B3-Flags', '0')

    # Store zipkin_trace_id and zipkin_span_id in the request object so that
    # they're still available once we leave the pyramid_zipkin tween. An example
    # is being able to log them in the pyramid exc_logger, which runs after all
    # tweens have been exited.
    request.zipkin_trace_id = get_trace_id(request)
    request.zipkin_span_id = span_id

    return ZipkinAttrs(
        trace_id=request.zipkin_trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        flags=flags,
        is_sampled=is_sampled,
    )


def get_binary_annotations(
    request: Request,
    response: Response,
) -> Dict[str, Optional[str]]:
    """Helper method for getting all binary annotations from the request.

    :param request: the Pyramid request object
    :param response: the Pyramid response object
    :returns: binary annotation dict of {str: str}
    """
    # use only @property of the request object
    # https://sourcegraph.com/search?q=repo:%5Egithub%5C.com/Pylons/webob$@1.8.7++file:%5Esrc/webob/request%5C.py$+@property&patternType=keyword&sm=0
    annotations = {
        'http.uri': request.path,
        'http.uri.qs': request.path_qs,
        'otel.library.name': __name__.split('.')[0],
        'otel.library.version': __version__,
    }

    if request.client_addr:
        annotations['client.address'] = request.client_addr

    if request.matched_route:
        annotations['http.route'] = request.matched_route.pattern

    # update attributes from request.environ object
    # https://sourcegraph.com/github.com/Pylons/webob@1.8.7/-/blob/docs/index.txt?L63-68
    request_env = request.environ
    _update_annotations_from_request_environ(request_env, annotations)

    if response:
        status_code = response.status_code
        if isinstance(status_code, int):
            annotations['http.response.status_code'] = str(status_code)
            annotations['response_status_code'] = str(status_code)
            if 100 <= status_code < 200:
                annotations['otel.status_code'] = 'Unset'
            elif 200 <= status_code < 300:
                annotations['otel.status_code'] = 'Ok'
            elif 300 <= status_code < 500:
                annotations['otel.status_code'] = 'Unset'
            else:
                annotations['otel.status_code'] = 'Error'

        else:
            annotations['otel.status_code'] = 'Error'
            annotations['otel.status_description'] = (
                f'Non-integer HTTP status code: {repr(status_code)}'
            )

    settings = request.registry.settings
    if 'zipkin.set_extra_binary_annotations' in settings:
        annotations.update(
            settings['zipkin.set_extra_binary_annotations'](request, response)
        )
    return annotations


def _update_annotations_from_request_environ(
        environ: Dict,
        annotations: Dict[str, Optional[str]]
) -> None:
    method = environ.get('REQUEST_METHOD', '').strip()
    if method:
        annotations['http.request.method'] = method

    flavor = environ.get('SERVER_PROTOCOL', '')
    if flavor:
        annotations['network.protocol.version'] = flavor

    path = environ.get('PATH_INFO')
    if path:
        annotations['url.path'] = path

    host_name = environ.get('SERVER_NAME')
    host_port = environ.get('SERVER_PORT')

    if host_name:
        annotations['server.address'] = host_name

    if host_port:
        annotations['server.port'] = str(host_port)

    url_scheme = environ.get('wsgi.url_scheme')
    if url_scheme:
        annotations['url.scheme'] = url_scheme

    user_agent = environ.get('HTTP_USER_AGENT')
    if user_agent:
        annotations['user_agent.original'] = user_agent

    query_string = environ.get('QUERY_STRING')
    if query_string:
        annotations['url.query'] = query_string
