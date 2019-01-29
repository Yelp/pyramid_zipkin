# -*- coding: utf-8 -*-
from py_zipkin.transport import BaseTransportHandler

from .app import main


class MockTransport(BaseTransportHandler):
    def __init__(self, *argv, **kwargs):
        super(BaseTransportHandler, self).__init__(*argv, **kwargs)
        self.output = []

    def get_max_payload_bytes(self):
        return None

    def send(self, msg):
        self.output.append(msg)


def generate_app_main(settings, firehose=False):
    normal_transport = MockTransport()
    firehose_transport = MockTransport()
    app_main = main({}, **settings)
    app_main.registry.settings['zipkin.transport_handler'] = normal_transport
    if firehose:
        app_main.registry.settings['zipkin.firehose_handler'] = firehose_transport
    return app_main, normal_transport, firehose_transport
