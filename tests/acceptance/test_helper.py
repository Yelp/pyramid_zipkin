# -*- coding: utf-8 -*-
from py_zipkin.thrift import zipkin_core
from py_zipkin.transport import BaseTransportHandler
from thriftpy.protocol.binary import read_list_begin
from thriftpy.protocol.binary import TBinaryProtocol
from thriftpy.transport import TMemoryBuffer


class MockTransport(BaseTransportHandler):
    def __init__(self, *argv, **kwargs):
        super(BaseTransportHandler, self).__init__(*argv, **kwargs)
        self.output = []

    def get_max_payload_bytes(self):
        return None

    def send(self, msg):
        self.output.append(msg)


def decode_thrift(encoded_spans):
    spans = []
    trans = TMemoryBuffer(encoded_spans)
    _, size = read_list_begin(trans)
    for _ in range(size):
        span_obj = zipkin_core.Span()
        span_obj.read(TBinaryProtocol(trans))
        spans.append(span_obj)

    return spans


def get_timestamps(span):
    timestamps = {}
    for ann in span['annotations']:
        timestamps[ann['value']] = ann.pop('timestamp')
    return timestamps


def remove_ip_fields(span):
    for ann in span['annotations']:
        ann['host'].pop('ipv4', None)
        ann['host'].pop('ipv6', None)

    for b_ann in span['binary_annotations']:
        b_ann['host'].pop('ipv4', None)
        b_ann['host'].pop('ipv6', None)


def massage_result_span(span_obj):
    """Remove stuff from span to make it comparable
    """
    # span = ast.literal_eval(str(span_obj))
    span = span_obj.__dict__
    span['annotations'] = [ann.__dict__ for ann in span['annotations']]
    for ann in span['annotations']:
        ann['host'] = ann['host'].__dict__
    span['binary_annotations'] = [
        bann.__dict__ for bann in span['binary_annotations']]
    for bann in span['binary_annotations']:
        bann['host'] = bann['host'].__dict__
    span['annotations'].sort(key=lambda ann: ann['value'])
    span['binary_annotations'].sort(key=lambda ann: ann['key'])
    remove_ip_fields(span)
    return span


def assert_extra_annotations(span, annotations):
    seen_extra_annotations = dict(
        (ann.value, ann.timestamp) for ann
        in span.annotations
        if ann.value not in ('ss', 'sr', 'cs', 'cr')
    )
    assert annotations == seen_extra_annotations


def assert_extra_binary_annotations(span, binary_annotations):
    seen_extra_binary_annotations = dict(
        (ann.key, ann.value) for ann in span.binary_annotations
        if ann.key not in (
            'http.uri',
            'http.uri.qs',
            'http.route',
            'response_status_code',
        )
    )
    assert binary_annotations == seen_extra_binary_annotations
