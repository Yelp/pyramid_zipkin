import random
import re
import struct
from typing import Dict
from typing import Optional

from py_zipkin.util import generate_random_64bit_string
from py_zipkin.zipkin import ZipkinAttrs
from pyramid.interfaces import IRoutesMapper
from pyramid.request import Request
from pyramid.response import Response


DEFAULT_REQUEST_TRACING_PERCENT = 0.5


def get_trace_id(request: Request) -> str:
    """Gets the trace id based on a request. If not present with the request,
    create a custom (depending on config: `zipkin.trace_id_generator`) or a
    completely random trace id.

    :param: current active pyramid request
    :returns: a 64-bit hex string
    """
    if 'X-B3-TraceId' in request.headers:
        trace_id = _convert_signed_hex(request.headers['X-B3-TraceId'])
        # Tolerates 128 bit X-B3-TraceId by reading the right-most 16 hex
        # characters (as opposed to overflowing a U64 and starting a new trace).
        trace_id = trace_id[-16:]
    elif 'zipkin.trace_id_generator' in request.registry.settings:
        trace_id = _convert_signed_hex(request.registry.settings[
            'zipkin.trace_id_generator'](request))
    else:
        trace_id = generate_random_64bit_string()

    return trace_id


def _convert_signed_hex(s: str) -> str:
    """Takes a signed hex string that begins with '0x' and converts it to
    a 16-character string representing an unsigned hex value.
    Examples:
        '0xd68adf75f4cfd13' => 'd68adf75f4cfd13'
        '-0x3ab5151d76fb85e1' => 'c54aeae289047a1f'
    """
    if s.startswith('0x') or s.startswith('-0x'):
        s = '{:x}'.format(struct.unpack('Q', struct.pack('q', int(s, 16)))[0])
    return s.zfill(16)


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
    route = request.matched_route.pattern if request.matched_route else ''

    annotations = {
        'http.uri': request.path,
        'http.uri.qs': request.path_qs,
        'http.route': route,
    }
    if response:
        annotations['response_status_code'] = str(response.status_code)

    settings = request.registry.settings
    if 'zipkin.set_extra_binary_annotations' in settings:
        annotations.update(
            settings['zipkin.set_extra_binary_annotations'](request, response)
        )
    return annotations
