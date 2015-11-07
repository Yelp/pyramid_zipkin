# -*- coding: utf-8 -*-

import logging
import time

from pyramid_zipkin.exception import ZipkinError
from pyramid_zipkin.thread_local import pop_zipkin_attrs
from pyramid_zipkin.thread_local import push_zipkin_attrs
from pyramid_zipkin.thrift_helper import annotation_list_builder
from pyramid_zipkin.thrift_helper import base64_thrift
from pyramid_zipkin.thrift_helper import binary_annotation_list_builder
from pyramid_zipkin.thrift_helper import create_span


zipkin_logger = logging.getLogger('pyramid_zipkin.logger')
zipkin_logger.setLevel(logging.DEBUG)


class ZipkinLoggingContext(object):
    """The main logging context manager which controls logging handler and
    stores the zipkin attributes on its creation.

    :type zipkin_attrs: :class:`pyramid_zipkin.request_helper.ZipkinAttrs`
    :type endpoint_attrs: :class:`pyramid_zipkin.zipkinCore.ttypes.Endpoint`
    :param log_handler: log handler to be attached to the module logger.
    :type log_handler: :class:`pyramid_zipkin.logging_helper.ZipkinLoggerHandler`
    :param request_path_qs: request path query stored in the span as `http.uri`
    :param request_method: Name of the service span created eg. GET, POST
    """
    def __init__(self, zipkin_attrs, endpoint_attrs, log_handler,
                 request_path_qs, request_method):
        self.zipkin_attrs = zipkin_attrs
        self.endpoint_attrs = endpoint_attrs
        self.handler = log_handler
        self.request_path_qs = request_path_qs
        self.request_method = request_method
        self.response_status_code = 0

    def __enter__(self):
        """Actions to be taken before request is handled.
        1) Attach `zipkin_logger` to :class:`ZipkingLoggerHandler` object.
        2) Push zipkin attributes to thread_local stack.
        3) Record the start timestamp.
        """
        zipkin_logger.addHandler(self.handler)
        push_zipkin_attrs(self.zipkin_attrs)
        self.start_timestamp = time.time()
        return self

    def __exit__(self, _type, _value, _traceback):
        """Actions to be taken post request handling.
        1) Record the end timestamp.
        2) Pop zipkin attributes from thread_local stack
        3) Detach `zipkin_logger` handler.
        4) And finally, if sampled, log the service annotations to scribe
        """
        self.log_spans()
        pop_zipkin_attrs()
        zipkin_logger.removeHandler(self.handler)

    def is_response_success(self):
        """Returns a boolean whether the response was a success
        """
        return 200 <= self.response_status_code <= 299

    def log_spans(self):
        """Main function to log all the annotations stored during the entire
        request. This is done if the request is sampled and the response was
        a success. It also logs the service `ss` and `sr` annotations.
        """
        if self.zipkin_attrs.is_sampled and self.is_response_success():
            for _, span in self.handler.spans.iteritems():
                annotations = annotation_list_builder(
                    span['annotations'], self.endpoint_attrs)
                binary_annotations = binary_annotation_list_builder(
                    span['binary_annotations'], self.endpoint_attrs)
                log_span(self.zipkin_attrs, span['span_name'], annotations,
                         binary_annotations, span['is_client'])

            end_timestamp = time.time()
            log_service_span(self.zipkin_attrs, self.start_timestamp,
                             end_timestamp, self.request_path_qs,
                             self.endpoint_attrs, self.request_method)


class ZipkinLoggerHandler(logging.StreamHandler, object):
    """Logger Handler to log span annotations to scribe.
    To connect to the handler, logger name must be 'pyramid_zipkin.logger'

    :param zipkin_attrs: tuple containing trace_id, span_id & is_sampled
    """

    def __init__(self, zipkin_attrs):
        super(ZipkinLoggerHandler, self).__init__()
        self.zipkin_attrs = zipkin_attrs
        self.spans = {}

    def store_span(
            self, span_name, is_client, annotations, binary_annotations):
        """Store the annotations into a dict and send them later.

        :param span_name: string name of the span to be used.
        :param is_client: boolean to decide whether it is a client/server span
        :param annotations: dict of annotations logged.
        :param binary_annotations: dict of binary annotations logged.

        .. note::

            If duplicate annotations are logged for the same span name, only
            the last one will be logged.
        """
        key = (span_name, is_client)
        if key in self.spans:
            self.spans[key]['annotations'].update(annotations)
            self.spans[key]['binary_annotations'].update(binary_annotations)
        else:
            self.spans[key] = {'annotations': annotations,
                               'binary_annotations': binary_annotations,
                               'span_name': span_name,
                               'is_client': is_client
                               }

    def emit(self, record):
        """Handle each record message.

        :param record: object containing the `msg` object.
                       Structure of record.msg should be the following:
                       ::

                           {
                               "annotations": {
                                        "cs": ts1,
                                        "cr": ts2,
                                        },
                               "binary_annotations": {
                                        "http.uri": "/foo/bar",
                                        },
                                "name": "foo_span",
                                "type": "client/service",
                            }

                        "type" if not included is considered a 'service' span;
                        i.e. annotations are added in the current span instead
                        of creating a new one (which is the case for 'client').
        """
        if not self.zipkin_attrs.is_sampled:
            return
        span_name = record.msg.get('name', 'span')
        annotations = record.msg.get('annotations', {})
        binary_annotations = record.msg.get('binary_annotations', {})
        if not annotations and not binary_annotations:
            raise ZipkinError("Atleast one of annotation/binary annotation has"
                              " to be provided for {0} span".format(span_name))
        is_client = record.msg.get('type', 'service') == 'client'
        self.store_span(span_name, is_client, annotations, binary_annotations)


def log_span(zipkin_attrs, span_name, annotations, binary_annotations,
             is_client):
    """Creates a span and logs it.
    """
    span = create_span(
        zipkin_attrs, span_name, annotations, binary_annotations, is_client)
    base64_thrift(span)
    # TODO: *************** ADD scribe LOG. ***************


def log_service_span(zipkin_attrs, start_timestamp, end_timestamp,
                     path, endpoint, method):
    """Logs a span with `ss` and `sr` annotations.
    """
    annotations = annotation_list_builder(
        {'sr': start_timestamp, 'ss': end_timestamp}, endpoint)
    binary_annotations = binary_annotation_list_builder(
        {'http.uri': path}, endpoint)
    log_span(zipkin_attrs, method, annotations, binary_annotations, False)
