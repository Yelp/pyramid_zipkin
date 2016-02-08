# -*- coding: utf-8 -*-

import logging
import time

from pyramid_zipkin.exception import ZipkinError
from pyramid_zipkin.thread_local import pop_zipkin_attrs
from pyramid_zipkin.thread_local import push_zipkin_attrs
from pyramid_zipkin.thrift_helper import annotation_list_builder
from pyramid_zipkin.thrift_helper import binary_annotation_list_builder
from pyramid_zipkin.thrift_helper import create_span
from pyramid_zipkin.thrift_helper import thrift_obj_in_bytes


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
        self.request_method = request.method
        self.registry_settings = request.registry.settings
        self.response_status_code = 0
        self.binary_annotations_dict = {}

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
            for span in self.handler.spans:
                annotations = annotation_list_builder(
                    span['annotations'], self.endpoint_attrs)
                binary_annotations = binary_annotation_list_builder(
                    span['binary_annotations'], self.endpoint_attrs)
                log_span(self.zipkin_attrs, span['span_name'],
                         self.registry_settings, annotations,
                         binary_annotations, span['is_client'])

            end_timestamp = time.time()
            log_service_span(self.zipkin_attrs, self.start_timestamp,
                             end_timestamp, self.binary_annotations_dict,
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
        self.spans = []

    def store_span(
            self, span_name, is_client, annotations, binary_annotations):
        """Store the annotations into the list and send them later.

        :param span_name: string name of the span to be used.
        :param is_client: boolean to decide whether it is a client/server span
        :param annotations: dict of annotations logged.
        :param binary_annotations: dict of binary annotations logged.
        """
        self.spans.append({'annotations': annotations,
                           'binary_annotations': binary_annotations,
                           'span_name': span_name,
                           'is_client': is_client
                           })

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


def get_binary_annotations(request, response):
    """Helper method for getting all binary annotations from the request.

    :param request: the Pyramid request object
    :param response: the Pyramid response object
    :returns: binary annotation dict of {str: str}
    """
    annotations = {'http.uri': request.path, 'http.uri.qs': request.path_qs}
    settings = request.registry.settings
    if 'zipkin.set_extra_binary_annotations' in settings:
        annotations.update(
            settings['zipkin.set_extra_binary_annotations'](request, response))
    return annotations


def log_span(zipkin_attrs, span_name, registry_settings, annotations,
             binary_annotations, is_client):
    """Creates a span and logs it.

    If `zipkin.transport_handler` config is set, it is used to act as a callback
    and log message is sent as a parameter.
    """
    span = create_span(
        zipkin_attrs, span_name, annotations, binary_annotations, is_client)
    message = thrift_obj_in_bytes(span)

    scribe_stream = registry_settings.get('zipkin.stream_name', 'zipkin')

    if 'zipkin.transport_handler' in registry_settings:
        return registry_settings['zipkin.transport_handler'](scribe_stream,
                                                             message)
    else:
        raise ZipkinError(
            "`zipkin.transport_handler` is a required config property, which"
            " is missing. It is a callback method which takes stream_name and"
            " a message as the params and logs message via scribe/kafka.")


def log_service_span(zipkin_attrs, start_timestamp, end_timestamp,
                     binary_annotations_dict, endpoint, method,
                     registry_settings):
    """Logs a span with `ss` and `sr` annotations.
    """
    annotations = annotation_list_builder(
        {'sr': start_timestamp, 'ss': end_timestamp}, endpoint)
    binary_annotations = binary_annotation_list_builder(
        binary_annotations_dict, endpoint)
    log_span(zipkin_attrs, method, registry_settings,
             annotations, binary_annotations, False)
