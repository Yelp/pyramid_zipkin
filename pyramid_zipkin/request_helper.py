# -*- coding: utf-8 -*-

import codecs
import os
import re
import struct
from collections import namedtuple

import six
from pyramid.interfaces import IRoutesMapper


DEFAULT_REQUEST_TRACING_PERCENT = 0.5


class ZipkinAttrs(namedtuple(
        'ZipkinAttrs', 'trace_id span_id parent_span_id flags is_sampled')):
    """
    Holds the basic attributes needed to log a zipkin trace

    :param trace_id: Unique trace id
    :param span_id: Span Id of the current request span
    :param parent_span_id: Parent span Id of the current request span
    :param flags: stores flags header. Currently unused
    :param is_sampled: pre-computed boolean whether the trace should be logged
    """


def generate_random_64bit_string():
    """Returns a 64 bit UTF-8 encoded string. In the interests of simplicity,
    this is always cast to a `str` instead of (in py2 land) a unicode string.
    Certain clients (I'm looking at you, Twisted) don't enjoy unicode headers.
    """
    return str(codecs.encode(os.urandom(8), 'hex_codec').decode('utf-8'))


def get_trace_id(request):
    """Gets the trace id based on a request. If not present with the request,
    create a custom (depending on config: `zipkin.trace_id_generator`) or a
    completely random trace id.

    :param: current active pyramid request
    :returns: a 64-bit hex string
    """
    if 'X-B3-TraceId' in request.headers:
        trace_id = request.headers['X-B3-TraceId']
    elif 'zipkin.trace_id_generator' in request.registry.settings:
        trace_id = request.registry.settings['zipkin.trace_id_generator'](request)
    else:
        trace_id = generate_random_64bit_string()

    # Backwards compatibility for <=v0.8.1
    # If the trace id is a hex value that starts with '0x' or '-0x',
    # convert to the unsigned form before proceeding.
    if trace_id.startswith('0x') or trace_id.startswith('-0x'):
        trace_id = _signed_hex_to_unsigned_hex(trace_id)
    trace_id = trace_id.zfill(16)

    return trace_id


def _signed_hex_to_unsigned_hex(s):
    """Takes a signed hex string that begins with '0x' and converts it to
    a 16-character string representing an unsigned hex value.

    Examples:
        '0xd68adf75f4cfd13' => 'd68adf75f4cfd13'
        '-0x3ab5151d76fb85e1' => 'c54aeae289047a1f'
    """
    return '{0:x}'.format(struct.unpack('Q', struct.pack('q', int(s, 16)))[0])


def should_not_sample_path(request):
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
        re.compile(r) if isinstance(r, six.string_types) else r
        for r in blacklisted_paths
    ]
    return any(r.match(request.path) for r in regexes)


def should_not_sample_route(request):
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


def should_sample_as_per_zipkin_tracing_percent(tracing_percent, req_id):
    """Calculate whether the request should be traced as per tracing percent.

    :param tracing_percent: value between 0.0 to 100.0
    :type tracing_percent: float
    :param req_id: unique request id of the request
    :returns: boolean whether current request should be sampled.
    """
    if tracing_percent == 0.0:  # Prevent the ZeroDivision
        return False
    inverse_frequency = int((1.0 / tracing_percent) * 100)
    return int(req_id, 16) % inverse_frequency == 0


def is_tracing(request):
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
            zipkin_tracing_percent, request.zipkin_trace_id)


def create_zipkin_attr(request):
    """Create ZipkinAttrs object from a request with sampled flag as True.
    Attaches lazy attribute `zipkin_trace_id` with request which is then used
    throughout the tween.

    :param request: pyramid request object
    :rtype: :class:`pyramid_zipkin.request_helper.ZipkinAttrs`
    """
    request.set_property(get_trace_id, 'zipkin_trace_id', reify=True)

    trace_id = request.zipkin_trace_id
    is_sampled = is_tracing(request)
    span_id = request.headers.get('X-B3-SpanId', generate_random_64bit_string())
    parent_span_id = request.headers.get('X-B3-ParentSpanId', None)
    flags = request.headers.get('X-B3-Flags', '0')
    return ZipkinAttrs(
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        flags=flags,
        is_sampled=is_sampled,
    )
