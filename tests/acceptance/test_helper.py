# -*- coding: utf-8 -*-
def get_timestamps(span):
    timestamps = {}
    for ann in span['annotations']:
        timestamps[ann['value']] = ann.pop('timestamp')
    return timestamps


def remove_ipv4(span):
    for ann in span['annotations']:
        ann['host'].pop('ipv4', None)

    for b_ann in span['binary_annotations']:
        b_ann['host'].pop('ipv4', None)


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
    remove_ipv4(span)
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
        if ann.key not in ('http.uri', 'http.uri.qs')
    )
    assert binary_annotations == seen_extra_binary_annotations
