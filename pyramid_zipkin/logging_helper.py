# -*- coding: utf-8 -*-

import logging
import time

from scribe import scribe
from thrift.transport import TTransport, TSocket
from thrift.protocol import TBinaryProtocol

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
    :param request: active pyramid request object
    """
    def __init__(self, zipkin_attrs, endpoint_attrs, log_handler, request):
        self.zipkin_attrs = zipkin_attrs
        self.endpoint_attrs = endpoint_attrs
        self.handler = log_handler
        self.request_path_qs = request.path_qs
        self.request_method = request.method
        self.registry_settings = request.registry.settings
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
                log_span(self.zipkin_attrs, span['span_name'],
                         self.registry_settings, annotations,
                         binary_annotations, span['is_client'])

            end_timestamp = time.time()
            log_service_span(self.zipkin_attrs, self.start_timestamp,
                             end_timestamp, self.request_path_qs,
                             self.endpoint_attrs, self.request_method,
                             self.registry_settings)


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


def log_span(zipkin_attrs, span_name, registry_settings, annotations,
             binary_annotations, is_client):
    """Creates a span and logs it.

    If `zipkin.scribe_handler` config is set, it is used to act as a callback
    and log message is sent as a parameter.
    """
    span = create_span(
        zipkin_attrs, span_name, annotations, binary_annotations, is_client)
    message = base64_thrift(span)

    scribe_stream = registry_settings.get('zipkin.scribe_stream_name', 'zipkin')

    if 'zipkin.scribe_handler' in registry_settings:
        return registry_settings['zipkin.scribe_handler'](scribe_stream, message)
    else:
        scribe_host = registry_settings['zipkin.scribe_host']
        scribe_port = registry_settings['zipkin.scribe_port']
        default_scribe_handler(scribe_host, scribe_port, scribe_stream, message)


def default_scribe_handler(host, port, stream_name, message):
    """Default scribe handler to send log message to scribe host

    :param host: scribe host to connect and send logs to.
    :param port: scribe port to connect to.
    :param stream_name: scribe stream name, default: zipkin.
    :param message: base64 encoded log span information

    :returns: return status code after sending to scribe. 0 means success.
    """
    socket = TSocket.TSocket(host, port)
    transport = TTransport.TFramedTransport(socket)
    protocol = TBinaryProtocol.TBinaryProtocol(
        trans=transport, strictRead=False, strictWrite=False)
    client = scribe.Client(protocol)
    transport.open()

    log_entry = scribe.LogEntry(stream_name, message)
    return client.Log(messages=[log_entry])


def log_service_span(zipkin_attrs, start_timestamp, end_timestamp,
                     path, endpoint, method, registry_settings):
    """Logs a span with `ss` and `sr` annotations.
    """
    annotations = annotation_list_builder(
        {'sr': start_timestamp, 'ss': end_timestamp}, endpoint)
    binary_annotations = binary_annotation_list_builder(
        {'http.uri': path}, endpoint)
    log_span(zipkin_attrs, method, registry_settings,
             annotations, binary_annotations, False)
