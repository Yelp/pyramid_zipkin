# -*- coding: utf-8 -*-

"""
This module contains utilities for support Zipkin distributed tracing system:

http://twitter.github.io/zipkin/
"""
from __future__ import absolute_import

import time

from pyramid_zipkin.logging_helper import get_binary_annotations
from pyramid_zipkin.logging_helper import zipkin_logger
from pyramid_zipkin.logging_helper import ZipkinLoggerHandler
from pyramid_zipkin.logging_helper import ZipkinLoggingContext
from pyramid_zipkin.request_helper import create_zipkin_attr
from pyramid_zipkin.request_helper import generate_random_64bit_string
from pyramid_zipkin.request_helper import ZipkinAttrs
from pyramid_zipkin.thread_local import get_zipkin_attrs
from pyramid_zipkin.thread_local import pop_zipkin_attrs
from pyramid_zipkin.thread_local import push_zipkin_attrs
from pyramid_zipkin.thrift_helper import create_endpoint


class ClientSpanContext(object):
    """In this context, each additional client span logged will have their
    parent span set to this client span's ID. It accomplishes that by
    attaching this client span's ID to the logger handler.

    Note: this contextmanager ONLY works within a pyramid_zipkin tween
    context. Outside this context, the proper logging handlers will
    not be set up.
    """
    def __init__(
        self, service_name, span_name='span',
        annotations=None, binary_annotations=None,
    ):
        """Enter the client context. Initializes a bunch of state related
        to this span.

        :param service_name: The name of the called service
        :param span_name: Optional name of span, defaults to 'span'
        :param annotations: Optional dict of str -> timestamp annotations
        :param binary_annotations: Optional dict of str -> str span attrs
        """
        self.service_name = service_name
        self.span_name = span_name
        self.annotations = annotations or {}
        self.binary_annotations = binary_annotations or {}

    def __enter__(self):
        """Enter the client context. All spans/annotations logged inside this
        context will be attributed to this client span.
        """
        zipkin_attrs = get_zipkin_attrs()
        self.is_sampled = zipkin_attrs is not None and zipkin_attrs.is_sampled
        if not self.is_sampled:
            return self

        self.start_timestamp = time.time()
        self.span_id = generate_random_64bit_string()
        # Put span ID on logging handler. Assume there's only a single handler
        # on the logger, since all logging should be set up in this package.
        self.handler = zipkin_logger.handlers[0]
        # Store the old parent_span_id, probably None, in case we have
        # nested ClientSpanContexts
        self.old_parent_span_id = self.handler.parent_span_id
        self.handler.parent_span_id = self.span_id
        # Push new zipkin attributes onto the threadlocal stack, so that
        # create_headers_for_new_span() performs as expected in this context.
        # The only difference is that span_id is this new client span's ID
        # and parent_span_id is the old span's ID.
        new_zipkin_attrs = ZipkinAttrs(
            trace_id=zipkin_attrs.trace_id,
            span_id=self.span_id,
            parent_span_id=zipkin_attrs.span_id,
            flags=zipkin_attrs.flags,
            is_sampled=zipkin_attrs.is_sampled,
        )
        push_zipkin_attrs(new_zipkin_attrs)
        return self

    def __exit__(self, _exc_type, _exc_value, _exc_traceback):
        if not self.is_sampled:
            return

        end_timestamp = time.time()
        # Put the old parent_span_id back on the handler
        self.handler.parent_span_id = self.old_parent_span_id
        # Pop off the new zipkin attrs
        pop_zipkin_attrs()
        self.annotations['cs'] = self.start_timestamp
        self.annotations['cr'] = end_timestamp
        # Store this client span on the logging handler object
        self.handler.store_client_span(
            span_name=self.span_name,
            service_name=self.service_name,
            annotations=self.annotations,
            binary_annotations=self.binary_annotations,
            span_id=self.span_id,
        )


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
        'X-B3-SpanId': generate_random_64bit_string(),
        'X-B3-ParentSpanId': zipkin_attrs.span_id,
        'X-B3-Flags': '0',
        'X-B3-Sampled': '1' if zipkin_attrs.is_sampled else '0',
    }
