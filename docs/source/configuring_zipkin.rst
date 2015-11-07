Configuring Zipkin
===================

All of the settings have a default functionality as well. These can be used to
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
-------------------------------------
    A method definition to generate a `trace_id` for the request.

    The method MUST take `request` as a parameter.



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
