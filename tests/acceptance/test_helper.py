import ast


def get_timestamps(span):
    timestamps = {}
    for ann in span['annotations']:
        timestamps[ann['value']] = ann.pop('timestamp')
    return timestamps


def remove_ipv4(span):
    for ann in span['annotations']:
        ann['host'].pop('ipv4')

    for b_ann in span['binary_annotations']:
        b_ann['host'].pop('ipv4')


def massage_result_span(span_obj):
    """Remove stuff from span to make it comparable
    """
    span = ast.literal_eval(str(span_obj))
    span['annotations'].sort(key=lambda ann: ann['value'])
    span['binary_annotations'].sort(key=lambda ann: ann['key'])
    remove_ipv4(span)
    return span
