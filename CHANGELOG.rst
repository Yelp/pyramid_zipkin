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
