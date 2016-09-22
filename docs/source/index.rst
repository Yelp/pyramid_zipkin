pyramid_zipkin documentation
============================

This project acts as a `Pyramid <http://docs.pylonsproject.org/en/latest/docs/pyramid.html>`_
tween by using `py_zipkin <https://github.com/Yelp/py_zipkin>`_ to facilitate creation of `zipkin <https://github.com/openzipkin/zipkin/wiki>`_ service spans.

Features include:

* Blacklisting specific route/paths from getting traced.

* ``zipkin_tracing_percent`` to control the percentage of requests getting sampled.

* Adds ``http.uri``, ``http.uri.qs``, and ``status_code`` binary annotations automatically for each trace.

* Allows configuration of additional arbitrary binary annotations.

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
