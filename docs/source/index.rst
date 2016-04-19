pyramid_zipkin documentation
============================

This project acts as a `Pyramid <http://docs.pylonsproject.org/en/latest/docs/pyramid.html>`_
tween to facilitate creation of `zipkin <https://github.com/openzipkin/zipkin/wiki>`_ service spans.

Features include:

* Blacklisting specific route/paths from getting traced.

* ``zipkin_tracing_percent`` to control the percentage of requests getting sampled.

* API ``create_headers_for_new_span`` to generate new client headers.

* API ``SpanContext`` for logging trees of spans in code.

* Adds ``http.uri`` and ``http.uri.qs`` binary annotations automatically for each trace.

* Allows configuration of arbitrary additional binary annotations.

* Allows logging of additional annotations and client spans at any point in request context.

Install
-------

.. code-block:: python

    pip install pyramid_zipkin

Usage
-----

In your service's webapp, you need to include:

.. code-block:: python

    config.include('pyramid_zipkin')

Contents:

.. toctree::
   :maxdepth: 2

   configuring_zipkin
   pyramid_zipkin
   changelog

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
