# -*- coding: utf-8 -*-

"""
This module contains utilities for support Zipkin distributed tracing system:

http://twitter.github.io/zipkin/
"""
from __future__ import absolute_import

from pyramid_zipkin.request_helper import create_zipkin_attr
from pyramid_zipkin.thread_local import get_zipkin_attrs
from pyramid_zipkin.thrift_helper import create_endpoint
from pyramid_zipkin.thrift_helper import generate_span_id
from pyramid_zipkin.logging_helper import get_binary_annotations
from pyramid_zipkin.logging_helper import ZipkinLoggerHandler
from pyramid_zipkin.logging_helper import ZipkinLoggingContext


def zipkin_tween(handler, registry):
    """
    Factory for pyramid tween to handle zipkin server logging.

    :param handler: pyramid request handler
    :param registry: pyramid app registry

    :returns: pyramid tween
    """
    def tween(request):
        zipkin_attrs = create_zipkin_attr(request)

        # If this request isn't sampled, don't go through the work
        # of initializing the rest of the zipkin attributes
        if not zipkin_attrs.is_sampled:
            return handler(request)

        # If the request IS sampled, we create thrift objects, store
        # thread-local variables, etc, to enter zipkin logging context
        thrift_endpoint = create_endpoint(request)
        log_handler = ZipkinLoggerHandler(zipkin_attrs)
        with ZipkinLoggingContext(zipkin_attrs, thrift_endpoint, log_handler,
                                  request) as context:
            response = handler(request)
            context.response_status_code = response.status_code
            context.binary_annotations_dict = get_binary_annotations(
                    request, response)

            return response

    return tween


def create_headers_for_new_span():
    """
    Generate the headers for a new zipkin span.

    .. note::

        If the method is not called from within a pyramid service call OR
        pyramid_zipkin is not included as a pyramid tween, empty dict will be
        returned back.

    :returns: dict containing (X-B3-TraceId, X-B3-SpanId, X-B3-ParentSpanId,
                X-B3-Flags and X-B3-Sampled) keys OR an empty dict.
    """
    zipkin_attrs = get_zipkin_attrs()

    if not zipkin_attrs:
        return {}

    return {
        'X-B3-TraceId': zipkin_attrs.trace_id,
        'X-B3-SpanId': generate_span_id(),
        'X-B3-ParentSpanId': zipkin_attrs.span_id,
        'X-B3-Flags': '0',
        'X-B3-Sampled': '1' if zipkin_attrs.is_sampled else '0',
    }
