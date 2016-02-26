Configuring pyramid_zipkin
==========================

These settings are mandatory and need to be provided for `pyramid_zipkin` to
work correctly:

1. zipkin.transport_handler
---------------------------
    A callback function which takes two parameters, the `stream name` and the
    `message data`. A sample method can be, something like this:

    A) FOR `kafka` TRANSPORT:

    .. code-block:: python

        from kafka import SimpleProducer, KafkaClient

        def kafka_handler(stream_name, message):

            kafka = KafkaClient('{0}:{1}'.format('localhost', 9092))
            producer = SimpleProducer(kafka, async=True)
            producer.send_messages(stream_name, message)

    Once the method is defined, it can be assigned like so:

    .. code-block:: python

        'zipkin.transport_handler': kafka_handler

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

    Once the method is defined, it can be assigned like so:

    .. code-block:: python

        'zipkin.transport_handler': scribe_handler

    The above example uses python package `facebook-scribe <https://pypi.python.org/pypi/facebook-scribe/>`_
    for the scribe apis but any similar package can do the work.

-------------------------------------------------------------------------

All below settings are optional and have a sane default functionality set. These can be used to
fine tune as per your use case.

1. zipkin.stream_name
---------------------
    The `stream_name` the message will be logged to via transport layer. It defaults to `zipkin`.


2. zipkin.blacklisted_paths
---------------------------
    A list of paths as strings, regex strings, or compiled regexes, any of which if matched with the
    request path will not be sampled. Pre-compiled regexes will be the fastest.
    Defaults to `[]`. Example:

    .. code-block:: python

        'zipkin.blacklisted_paths': [r'^/status/?',]


3. zipkin.blacklisted_routes
----------------------------
    A list of routes as strings any of which if matched with the request route
    will not be sampled. Defaults to `[]`. Example:

    .. code-block:: python

        'zipkin.blacklisted_routes': ['some_internal_route',]


4. zipkin.tracing_percent
-------------------------
    A number between 0.0 and 100.0 to control how many request calls get sampled.
    Defaults to `0.50`. Example:

    .. code-block:: python

        'zipkin.tracing_percent': 100.0  # Trace all the calls.


5. zipkin.trace_id_generator
----------------------------
    A method definition to generate a `trace_id` for the request. By default,
    it creates a randon trace id otherwise.

    The method MUST take `request` as a parameter (so that you can make trace
    id deterministic).


6. zipkin.set_extra_binary_annotations
--------------------------------------
    A method that takes `request` and `response` objects as parameters
    and produces extra binary annotations. If this config is omitted,
    only `http.uri` and `http.uri.qs` are added as binary annotations.
    The return value of the callback must be a dictionary, and all keys
    and values must be in `str` format. Example:

    .. code-block:: python

        def set_binary_annotations(request, response):
            return {'view': get_view(request)}

        settings['zipkin.set_extra_binary_annotations'] = set_binary_annotations


These settings can be added like so:

.. code-block:: python

        def main(global_config, **settings):
            # ...
            settings['zipkin.blacklisted_paths'] = [r'^/foo/?']
            settings['zipkin.blacklisted_routes'] = ['bar']
            settings['zipkin.trace_id_generator'] = lambda req: '0x42'
            settings['zipkin.set_extra_binary_annotations'] = lambda req, resp: {'attr': str(req.attr)}
            # ...and so on with the other settings...
            config = Configurator(settings=settings)
            config.include('zipkin')
