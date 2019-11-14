0.26.0 (2019-11-14)
-------------------
- Add zipkin_span_id to the request object.

0.25.1 (2019-09-16)
-------------------
- Path and route blacklists now work also for firehose traces

0.25.0 (2019-02-28)
-------------------
- Remove `zipkin.always_emit_zipkin_headers` config option. Rather than using
  set_property to add the trace_id to the request, we now do a simple assignment
  which is way faster and removes the need for that flag.

0.24.1 (2019-02-25)
-------------------
- Update tween to support py-zipkin 0.18+

0.24.0 (2019-01-29)
-------------------
- Add `zipkin.encoding` param to allow specifying the output span encoding.

0.23.0 (2018-12-11)
-------------------
- Add post_handler_hook to the tween.

0.22.0 (2018-10-02)
-------------------
- Set `zipkin.use_pattern_as_span_name` to use the pyramid route pattern
  as span_name rather than the raw url.
- Requires py_zipkin >= 0.13.0.

0.21.1 (2018-06-03)
-------------------
- Use renamed py_zipkin.storage interface
- Remove deprecated logger.debug() usage in tests
- Require py_zipkin >= 0.13.0

0.21.0 (2018-03-09)
-------------------
- Added support for http.route annotation

0.20.3 (2018-03-08)
-------------------
- Add max_span_batch_size to the zipkin tween settings.

0.20.2 (2018-02-20)
-------------------
- Require py_zipkin >= 0.11.0

0.20.1 (2018-02-13)
-------------------
- Added support for experimental firehose mode

0.20.0 (2018-02-09)
-------------------
- Added support for using a request-specific stack for storing zipkin attributes.

0.19.2 (2017-08-17)
-------------------
- Trace context is again propagated for non-sampled requests.

0.19.1 (2017-06-02)
-------------------
- Modified tween.py to include host and port when creating a zipkin span.

0.19.0 (2017-06-01)
-------------------
- Added zipkin.always_emit_zipkin_headers config flag.
- Skip zipkin_span context manager if the request is not being sampled
  to improve performance and avoid unnecessary work.

0.18.2 (2017-03-06)
-------------------
- Using new update_binary_annotations functions from py_zipkin.
- Requires py_zipkin >= 0.7.0

0.18.1 (2017-02-06)
-------------------
- No changes

0.18.0 (2017-02-06)
-------------------
- Add automatic timestamp/duration reporting for root server span. Also added
  functionality for individual services to override this setting in configuration.

0.17.0 (2016-12-16)
-------------------
- Add registry setting to force py-zipkin to add a logging annotation to server
  traces. Requires py-zipkin >= 0.4.4.

0.16.1 (2016-10-14)
-------------------
- support for configuring custom versions of create_zipkin_attr and is_tracing
  through the pyramid registry.

0.16.0 (2016-10-06)
-------------------
- Fix sample rate bug and make sampling be random and not depend on request id.

0.15.0 (2016-09-29)
-------------------
- Make `get_trace_id` function more defensive about what types of trace
  ids it accepts. Converts "0x..." and "-0x..." IDs to remove the leading
  "Ox"s

0.14.0 (2016-09-29)
-------------------
- Make `zipkin.transport_handler` a function that takes two arguments, a
  stream_name and a message.

0.13.1 (2016-09-21)
-------------------
- Alias `create_headers_for_new_span` to `create_http_headers_for_new_span`
  for backwards compatibility.

0.13.0 (2016-09-12)
-------------------
- Moved non-pyramid and zipkin-only code to py_zipkin package
- 'zipkin.transport_handler' now only takes a single message parameter
- `create_headers_for_new_span` is moved to py_zipkin and renamed to
  `create_http_headers_for_new_span`

0.12.3 (2016-07-27)
-------------------
- Fix coverage command invocation to be compatible with coverage v4.2

0.12.2 (2016-07-15)
-------------------
- make "service_name" default to "unknown" when not found in registry

0.12.1 (2016-07-08)
-------------------
- Add @zipkin_span decorator for logging functions as spans

0.11.1 (2016-04-28)
-------------------
- Binary annotation values are converted to str
- Removed restriction where only successful status codes are logged
- Added status code as a default binary annotation
- Prevent errors when ZipkinAttrs doesn't exist (usually in multithreaded environments)
- pyramid-zipkin is a pure python package

0.11.0 (2016-04-19)
-------------------
- Renames ClientSpanContext to SpanContext, adds 'ss' and 'sr' annotations.

0.10.0 (2016-04-12)
-------------------
- Always generate ZipkinAttrs, even when a request isn't sampled.

0.9.2 (2016-04-07)
------------------
- Don't set parent_span_id on root span

0.9.1 (2016-03-29)
------------------
- Made generate_random_64bit_string always return str, not unicode

0.9.0 (2016-03-27)
------------------
- Fixed bug where headers were not 64-bit unsigned hex strings.
- Added ClientSpanContext, that lets users log arbitrary trees of
  client spans.
- Deprecates "is_client=True" debug logging key in favor of a
  non-None "service_name" key for indicating that a span logged
  is a new client span.
- Batches up additional annotations in client before sending
  to the collector.

0.8.1 (2016-03-02)
------------------
- Spans without a span ID will generate a new span ID by default.

0.8.0 (2016-03-01)
------------------
- Add ability to override "service_name" attribute when logging client
  spans.

0.7.1 (2016-02-26)
------------------
- Don't re-compile path regexes

0.7.0 (2016-02-24)
------------------
- Don't enter ZipkinLoggingContext if request is not sampled.

0.6.0 (2016-02-06)
------------------
- Fix bug which was squashing identical span names.
- over=EXCVIEW ordering instead of over=MAIN

0.5.0 (2016-01-14)
------------------
- Add support for `set_extra_binary_annotations` callback.

0.4.0 (2016-01-07)
------------------
- Add `http.uri.qs` annotation which includes query string, `http.uri` doesn't.

0.3.0 (2015-12-29)
------------------
- Change config parameters to be generic for scribe/kafka transport.

0.2.2 (2015-12-09)
------------------
- Compatible with py33, py34. Replaced Thrift with thriftpy.

0.1.2 (2015-12-03)
------------------
- Re-assign empty list to threading_local.requests if attr not present instead of
  globally assigning empty list.

0.1.0 (2015-11-08)
------------------
- pyramid-zipkin setup.
