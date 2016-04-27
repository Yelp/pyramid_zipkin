# -*- coding: utf-8 -*-
import os
import socket
import struct

import thriftpy
from thriftpy.transport import TMemoryBuffer
from thriftpy.protocol.binary import TBinaryProtocol


thrift_filepath = os.path.join(os.path.dirname(__file__),
                               'thrift/zipkinCore.thrift')
zipkin_core = thriftpy.load(thrift_filepath, module_name="zipkinCore_thrift")


dummy_endpoint = zipkin_core.Endpoint()


def create_annotation(timestamp, value, host):
    """
    Create a zipkin annotation object

    :param timestamp: timestamp of when the annotation occured in microseconds
    :param value: name of the annotation, such as 'sr'
    :param host: zipkin endpoint object

    :returns: zipkin annotation object
    """
    return zipkin_core.Annotation(timestamp=timestamp, value=value, host=host)


def create_binary_annotation(key, value, annotation_type, host):
    """
    Create a zipkin binary annotation object

    :param key: name of the annotation, such as 'http.uri'
    :param value: value of the annotation, such as a URI
    :param annotation_type: type of annotation, such as AnnotationType.I32
    :param host: zipkin endpoint object

    :returns: zipkin binary annotation object
    """
    return zipkin_core.BinaryAnnotation(
        key=key, value=value, annotation_type=annotation_type, host=host)


def create_endpoint(request):
    """Create a zipkin endpoint object based on a request

    :param request: pyramid request object
    :returns: zipkin endpoint object
    """
    service_name = request.registry.settings['service_name']
    host = socket.gethostbyname(socket.gethostname())
    port = request.server_port

    # Convert ip address to network byte order
    ipv4 = struct.unpack('!i', socket.inet_aton(host))[0]
    port = int(port)
    # Zipkin passes unsigned values in signed types because Thrift has no
    # unsigned types, so we have to convert the value.
    port = struct.unpack('h', struct.pack('H', port))[0]

    return zipkin_core.Endpoint(
        ipv4=ipv4, port=port, service_name=service_name)


def copy_endpoint_with_new_service_name(endpoint, service_name):
    """Copies a copy of a given endpoint with a new service name.
    This should be very fast, on the order of several microseconds.

    :param endpoint: existing zipkin_core.Endpoint object
    :param service_name: str of new service name
    :returns: zipkin endpoint object
    """
    return zipkin_core.Endpoint(
        ipv4=endpoint.ipv4,
        port=endpoint.port,
        service_name=service_name,
    )


def annotation_list_builder(annotations, host):
    """
    Reformat annotations dict to return list of corresponding zipkin_core objects.

    :param annotations: dict containing key as annotation name,
                        value being timestamp in seconds(float).
    :type host: :class:`zipkin_core.Endpoint`
    :returns: a list of annotation zipkin_core objects
    :rtype: list
    """
    return [create_annotation(
        int(timestamp * 1000000), key, host)
        for key, timestamp in annotations.items()]


def binary_annotation_list_builder(binary_annotations, host):
    """
    Reformat binary annotations dict to return list of zipkin_core objects. The
    value of the binary annotations MUST be in string format.

    :param binary_annotations: dict with key, value being the name and value
                               of the binary annotation being logged.
    :type host: :class:`zipkin_core.Endpoint`
    :returns: a list of binary annotation zipkin_core objects
    :rtype: list
    """
    # TODO: Remove the type hard-coding of STRING to take it as a param option.
    ann_type = zipkin_core.AnnotationType.STRING
    return [
        create_binary_annotation(key, str(value), ann_type, host)
        for key, value in binary_annotations.items()
    ]


def create_span(
    span_id,
    parent_span_id,
    trace_id,
    span_name,
    annotations,
    binary_annotations,
):
    """Takes a bunch of span attributes and returns a thriftpy representation
    of the span.
    """
    span_dict = {
        "trace_id": unsigned_hex_to_signed_int(trace_id),
        "name": span_name,
        "id": unsigned_hex_to_signed_int(span_id),
        "annotations": annotations,
        "binary_annotations": binary_annotations,
    }
    if parent_span_id:
        span_dict["parent_id"] = unsigned_hex_to_signed_int(parent_span_id)
    return zipkin_core.Span(**span_dict)


def thrift_obj_in_bytes(thrift_obj):  # pragma: no cover
    """
    Returns TBinaryProtocol encoded Thrift object.

    :param thrift_obj: thrift object to encode
    :returns: thrift object in TBinaryProtocol format bytes.
    """
    trans = TMemoryBuffer()
    thrift_obj.write(TBinaryProtocol(trans))

    return bytes(trans.getvalue())


def unsigned_hex_to_signed_int(hex_string):
    """Converts a 64-bit hex string to a signed int value.

    This is due to the fact that Apache Thrift only has signed values.

    Examples:
        '17133d482ba4f605' => 1662740067609015813
        'b6dbb1c2b362bf51' => -5270423489115668655
    Examples for backwards compatibility with signed hex strings:
        '0x4f18a03ad0031fe9' => 5699481502895775721
        '-0x4f18a03ad0031fe9' => -5699481502895775721

    :param hex_string: the string representation of a zipkin ID
    :returns: signed int representation
    """
    # Backwards compatibility with ids generated by previous versions
    if hex_string.startswith('-0x') or hex_string.startswith('0x'):
        return int(hex_string, 16)
    return struct.unpack('q', struct.pack('Q', int(hex_string, 16)))[0]
