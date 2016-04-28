# -*- coding: utf-8 -*-
import logging
import time
from collections import defaultdict

from pyramid_zipkin.exception import ZipkinError
from pyramid_zipkin.request_helper import generate_random_64bit_string
from pyramid_zipkin.thrift_helper import annotation_list_builder
from pyramid_zipkin.thrift_helper import binary_annotation_list_builder
from pyramid_zipkin.thrift_helper import copy_endpoint_with_new_service_name
from pyramid_zipkin.thrift_helper import create_span
from pyramid_zipkin.thrift_helper import thrift_obj_in_bytes


zipkin_logger = logging.getLogger('pyramid_zipkin.logger')
zipkin_logger.setLevel(logging.DEBUG)


class ZipkinLoggingContext(object):
    """The main logging context manager which controls logging handler and
    stores the zipkin attributes on its creation.

    :type zipkin_attrs: :class:`pyramid_zipkin.request_helper.ZipkinAttrs`
    :type thrift_endpoint: :class:`pyramid_zipkin.zipkinCore.ttypes.Endpoint`
    :param log_handler: log handler to be attached to the module logger.
    :type log_handler: :class:`pyramid_zipkin.logging_helper.ZipkinLoggerHandler`
    :param request: active pyramid request object
    """
    def __init__(self, zipkin_attrs, thrift_endpoint, log_handler, request):
        self.zipkin_attrs = zipkin_attrs
        self.thrift_endpoint = thrift_endpoint
        self.handler = log_handler
        self.request_method = request.method
        self.request_path = request.path
        self.registry_settings = request.registry.settings
        self.response_status_code = 0
        self.binary_annotations_dict = {}

    def __enter__(self):
        """Actions to be taken before request is handled.
        1) Attach `zipkin_logger` to :class:`ZipkingLoggerHandler` object.
        2) Record the start timestamp.
        """
        zipkin_logger.addHandler(self.handler)
        self.start_timestamp = time.time()
        return self

    def __exit__(self, _type, _value, _traceback):
        """Actions to be taken post request handling.
        1) Log the service annotations to scribe.
        2) Detach `zipkin_logger` handler.
        """
        self.log_spans()
        zipkin_logger.removeHandler(self.handler)

    def log_spans(self):
        """Main function to log all the annotations stored during the entire
        request. This is done if the request is sampled and the response was
        a success. It also logs the service `ss` and `sr` annotations.
        """
        if self.zipkin_attrs.is_sampled:
            # Collect additional annotations from the logging handler
            annotations_by_span_id = defaultdict(dict)
            binary_annotations_by_span_id = defaultdict(dict)
            for msg in self.handler.extra_annotations:
                span_id = msg['parent_span_id'] or self.zipkin_attrs.span_id
                # This should check if these are non-None
                annotations_by_span_id[span_id].update(msg['annotations'])
                binary_annotations_by_span_id[span_id].update(
                    msg['binary_annotations']
                )

            # Collect, annotate, and log client spans from the logging handler
            for span in self.handler.client_spans:
                # The parent_span_id is either the parent ID set in the
                # logging handler or the current Zipkin context's span ID.
                parent_span_id = (
                    span['parent_span_id'] or
                    self.zipkin_attrs.span_id
                )
                # A new client span's span ID can be overridden
                span_id = span['span_id'] or generate_random_64bit_string()
                endpoint = copy_endpoint_with_new_service_name(
                    self.thrift_endpoint, span['service_name']
                )
                # Collect annotations both logged with the new spans and
                # logged in separate log messages.
                annotations = span['annotations']
                annotations.update(annotations_by_span_id[span_id])
                binary_annotations = span['binary_annotations']
                binary_annotations.update(binary_annotations_by_span_id[span_id])
                # Create serializable thrift objects of annotations
                thrift_annotations = annotation_list_builder(
                    annotations, endpoint
                )
                thrift_binary_annotations = binary_annotation_list_builder(
                    binary_annotations, endpoint
                )

                log_span(
                    span_id=span_id,
                    parent_span_id=parent_span_id,
                    trace_id=self.zipkin_attrs.trace_id,
                    span_name=span['span_name'],
                    annotations=thrift_annotations,
                    binary_annotations=thrift_binary_annotations,
                    registry_settings=self.registry_settings,
                )

            # Collect extra annotations for server span, then log it.
            extra_annotations = annotations_by_span_id[self.zipkin_attrs.span_id]
            extra_binary_annotations = binary_annotations_by_span_id[
                self.zipkin_attrs.span_id
            ]
            annotations = dict(
                sr=self.start_timestamp,
                ss=time.time(),
                **extra_annotations
            )
            thrift_annotations = annotation_list_builder(
                annotations,
                self.thrift_endpoint,
            )

            # Binary annotations can be set through debug messages or the
            # set_extra_binary_annotations registry setting.
            self.binary_annotations_dict.update(extra_binary_annotations)
            thrift_binary_annotations = binary_annotation_list_builder(
                self.binary_annotations_dict,
                self.thrift_endpoint,
            )

            span_name = "{0} {1}".format(
                self.request_method, self.request_path)
            log_span(
                span_id=self.zipkin_attrs.span_id,
                parent_span_id=self.zipkin_attrs.parent_span_id,
                trace_id=self.zipkin_attrs.trace_id,
                span_name=span_name,
                annotations=thrift_annotations,
                binary_annotations=thrift_binary_annotations,
                registry_settings=self.registry_settings,
            )


class ZipkinLoggerHandler(logging.StreamHandler, object):
    """Logger Handler to log span annotations or additional client spans to
    scribe. To connect to the handler, logger name must be
    'pyramid_zipkin.logger'.

    :param zipkin_attrs: ZipkinAttrs namedtuple object
    """

    def __init__(self, zipkin_attrs):
        super(ZipkinLoggerHandler, self).__init__()
        # If parent_span_id is set, the application is in a logging context
        # where each additional client span logged has this span as its parent.
        # This is to allow logging of hierarchies of spans instead of just
        # single client spans. See the SpanContext class.
        self.parent_span_id = None
        self.zipkin_attrs = zipkin_attrs
        self.client_spans = []
        self.extra_annotations = []

    def store_client_span(
        self, span_name, service_name,
        annotations, binary_annotations, span_id=None,
    ):
        """Just a way of exposing how to store new client spans on this
        logging handler.
        """
        self.client_spans.append({
            'span_name': span_name,
            'service_name': service_name,
            'parent_span_id': self.parent_span_id,
            'span_id': span_id,
            'annotations': annotations,
            'binary_annotations': binary_annotations,
        })

    def emit(self, record):
        """Handle each record message. This function is called whenever
        zipkin_logger.debug() is called.

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
                "service_name": "myService",
            }

            Keys:
            - annotations: str -> timestamp annotations
            - binary_annotations: str -> str binary annotations
              (One of either annotations or binary_annotations is required)
            - name: str of new span name; only used if service-name is also
              specified.
            - service_name: str of new client span's service name.

            If service_name is specified, this log msg is considered to
            represent a new client span. If service_name is omitted, this is
            considered additional annotation for the currently active
            "parent span" (either the server span or the parent client span
            inside a SpanContext).
        """
        if not self.zipkin_attrs.is_sampled:
            return
        span_name = record.msg.get('name', 'span')
        annotations = record.msg.get('annotations', {})
        binary_annotations = record.msg.get('binary_annotations', {})
        if not annotations and not binary_annotations:
            raise ZipkinError(
                "Atleast one of annotation/binary annotation has"
                " to be provided for {0} span".format(span_name)
            )
        service_name = record.msg.get('service_name', None)
        # Presence of service_name means new client span.
        if service_name is not None:
            self.store_client_span(
                span_name=span_name,
                service_name=service_name,
                annotations=annotations,
                binary_annotations=binary_annotations,
            )
        else:
            self.extra_annotations.append({
                'annotations': annotations,
                'binary_annotations': binary_annotations,
                'parent_span_id': self.parent_span_id,
            })


def get_binary_annotations(request, response):
    """Helper method for getting all binary annotations from the request.

    :param request: the Pyramid request object
    :param response: the Pyramid response object
    :returns: binary annotation dict of {str: str}
    """
    annotations = {
        'http.uri': request.path,
        'http.uri.qs': request.path_qs,
        'response_status_code': str(response.status_code),
    }
    settings = request.registry.settings
    if 'zipkin.set_extra_binary_annotations' in settings:
        annotations.update(
            settings['zipkin.set_extra_binary_annotations'](request, response))
    return annotations


def log_span(
    span_id, parent_span_id, trace_id, span_name,
    annotations, binary_annotations,
    registry_settings,
):
    """Creates a span and logs it. Uses the required registry setting of
    `zipkin.transport_handler` to log the span.
    """
    span = create_span(
        span_id, parent_span_id, trace_id, span_name,
        annotations, binary_annotations,
    )
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
