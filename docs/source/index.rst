pyramid_zipkin documentation
========================

This project acts as a pyramid tween to faciliate creation of zipkin client and service spans.

Features include:

* Blacklist specific route/paths from getting traced.

* `zipkin_tracing_percent` in registry controls the %age of requests gettings sampled.

* API `create_headers_for_new_span` to generate new client headers.

* Use logger `pyramid_zipkin.logger` to log client spans.

Contents:

.. toctree::
   :maxdepth: 2

   configuring_zipkin
   pyramid_zipkin

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
