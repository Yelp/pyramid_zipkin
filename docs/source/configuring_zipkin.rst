Configuring Zipkin
===================

These settings are mandatory and need to be provided for `pyramid_zipkin` to
work correctly:

1) zipkin.scribe_handler
------------------------
    A callback function which takes two parameters, the stream name and the
    message data. A sample of the method can be, something like this:

    .. code-block:: python

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

            log_entry = scribe.LogEntry(stream_name, message)
            result = client.Log(messages=[log_entry])
            if result == 0:
              print 'success'

    Once the method is defined, it can be assigned like so:

    .. code-block::

        'zipkin.scribe_handler': scribe_handler

    The above example uses python package `facebook-scribe <https://pypi.python.org/pypi/facebook-scribe/>`_
    for the scribe apis but any similar package can do the work.


All below settings are optional and have a sane default functionality set. These can be used to
fine tune as per your use case.

1) zipkin.blacklisted_paths
---------------------------
    A list of paths as strings (accepts regex) any of which if matched with the
    request path will not be sampled.

2) zipkin.blacklisted_routes
----------------------------
    A list of routes as strings any of which if matched with the request route
    will not be sampled.


3) zipkin.trace_id_generator
----------------------------
    A method definition to generate a `trace_id` for the request.

    The method MUST take `request` as a parameter.

4) zipkin.scribe_stream_name
----------------------------
    The scribe `stream_name` the message will be logged to. It defaults to `zipkin`.

These settings can be added like so:

.. code-block:: python

        def main(global_config, **settings):
            # ...
            settings['zipkin.blacklisted_paths'] = [r'^/foo/?']
            settings['zipkin.blacklisted_routes'] = ['bar']
            settings['zipkin.trace_id_generator'] = lambda req: '0x42'
            # ...and so on with the other settings...
            config = Configurator(settings=settings)
            config.include('zipkin')
