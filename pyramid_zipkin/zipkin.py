from py_zipkin.zipkin import create_http_headers_for_new_span  # pragma: no cover


# Backwards compatibility for places where pyramid_zipkin is unpinned
create_headers_for_new_span = create_http_headers_for_new_span  # pragma: no cover
