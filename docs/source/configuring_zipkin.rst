Configuring pyramid_zipkin
==========================

Required configuration settings
-------------------------------

zipkin.transport_handler
~~~~~~~~~~~~~~~~~~~~~~~~
    A callback function which takes a single `message data` parameter.
    A sample method can be something like this:

    A) FOR `kafka` TRANSPORT:

    .. code-block:: python

        from kafka import SimpleProducer, KafkaClient

        def kafka_handler(stream_name, message):

            kafka = KafkaClient('{0}:{1}'.format('localhost', 9092))
            producer = SimpleProducer(kafka, async=True)
            producer.send_messages(stream_name, message)

    The above example uses python package `kafka-python <https://pypi.python.org/pypi/kafka-python>`_.

    B) FOR `scribe` TRANSPORT:

    .. code-block:: python

        import base64
        from scribe import scribe
        from thrift.transport import TTransport, TSocket
        from thrift.protocol import TBinaryProtocol

        def scribe_handler(stream_name, message):
            socket = TSocket.TSocket(host="HOST", port=9999)
            transport = TTransport.TFramedTransport(socket)
            protocol = TBinaryProtocol.TBinaryProtocol(
                trans=transport, strictRead=False, strictWrite=False)
            client = scribe.Client(protocol)
            transport.open()

            message_b64 = base64.b64encode(message).strip()
            log_entry = scribe.LogEntry(stream_name, message_b64)
            result = client.Log(messages=[log_entry])
            if result == 0:
              print 'success'

    The above example uses python package
    `facebook-scribe <https://pypi.python.org/pypi/facebook-scribe/>`_
    for the scribe APIs but any similar package can do the work.


Optional configuration settings
-------------------------------

All below settings are optional and have a sane default functionality set.
These can be used to fine tune as per your use case.

service_name
~~~~~~~~~~~~~~~
    A string representing the name of the service under instrumentation.
    It defaults to `unknown`.


zipkin.blacklisted_paths
~~~~~~~~~~~~~~~~~~~~~~~~~~~
    A list of paths as strings, regex strings, or compiled regexes, any of
    which if matched with the request path will not be sampled. Pre-compiled
    regexes will be the fastest. Defaults to `[]`. Example:

    .. code-block:: python

        'zipkin.blacklisted_paths': [r'^/status/?',]


zipkin.blacklisted_routes
~~~~~~~~~~~~~~~~~~~~~~~~~
    A list of routes as strings any of which if matched with the request route
    will not be sampled. Defaults to `[]`. Example:

    .. code-block:: python

        'zipkin.blacklisted_routes': ['some_internal_route',]


zipkin.stream_name
~~~~~~~~~~~~~~~~~~
    A log name to log Zipkin spans to. Defaults to 'zipkin'.


zipkin.tracing_percent
~~~~~~~~~~~~~~~~~~~~~~
    A number between 0.0 and 100.0 to control how many request calls get sampled.
    Defaults to `0.50`. Example:

    .. code-block:: python

        'zipkin.tracing_percent': 100.0  # Trace all the calls.


zipkin.trace_id_generator
~~~~~~~~~~~~~~~~~~~~~~~~~
    A method definition to generate a `trace_id` for the request. This is
    useful if you, say, have a unique_request_id you'd like to preserve.
    The trace_id must be a 64-bit hex string (e.g. '17133d482ba4f605').
    By default, it creates a random trace id.

    The method MUST take `request` as a parameter (so that you can make trace
    id deterministic).


zipkin.create_zipkin_attr
~~~~~~~~~~~~~~~~~~~~~~~~~
    A method that takes `request` and creates a ZipkinAttrs object. This
    can be used to generate span_id, parent_id or other ZipkinAttrs fields
    based on request parameters.

    The method MUST take `request` as a parametr and return a ZipkinAttrs
    object.


zipkin.is_tracing
~~~~~~~~~~~~~~~~~
    A method that takes `request` and determines if the request should be
    traced. This can be used to determine if a request is traced based on
    custom application specific logic.

    The method MUST take `request` as a parameter and return a Boolean.


zipkin.set_extra_binary_annotations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    A method that takes `request` and `response` objects as parameters
    and produces extra binary annotations. If this config is omitted,
    only `http.uri` and `http.uri.qs` are added as binary annotations.
    The return value of the callback must be a dictionary, and all keys
    and values must be in `str` format. Example:

    .. code-block:: python

        def set_binary_annotations(request, response):
            return {'view': get_view(request)}

        settings['zipkin.set_extra_binary_annotations'] = set_binary_annotations


zipkin.always_emit_zipkin_headers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Whether to forward the Zipkin's headers if the request is not being
    sampled. Defaults to True.

    Set to False if you're really concerned with performance as it'll save you
    about 300us on every non-traced request.


Configuring your application
----------------------------

These settings can be added at Pyramid application setup like so:

.. code-block:: python

        def main(global_config, **settings):
            # ...
            settings['service_name'] = 'zipkin'
            settings['zipkin.transport_handler'] = scribe_handler
            settings['zipkin.stream_name'] = 'zipkin_log'
            settings['zipkin.blacklisted_paths'] = [r'^/foo/?']
            settings['zipkin.blacklisted_routes'] = ['bar']
            settings['zipkin.trace_id_generator'] = lambda req: '0x42'
            settings['zipkin.set_extra_binary_annotations'] = lambda req, resp: {'attr': str(req.attr)}
            # ...and so on with the other settings...
            config = Configurator(settings=settings)
            config.include('pyramid_zipkin')
