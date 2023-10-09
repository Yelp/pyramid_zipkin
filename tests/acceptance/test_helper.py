from py_zipkin.transport import BaseTransportHandler

from .app import main


class MockTransport(BaseTransportHandler):
    def __init__(self, *argv, **kwargs):
        super(BaseTransportHandler, self).__init__(*argv, **kwargs)
        self.output = []

    def get_max_payload_bytes(self):
        return None

    def send(self, payload):
        self.output.append(payload)

    def get_payloads(self):
        """Returns the encoded spans that were sent.

        Spans are batched before being sent, so most of the time the returned
        list will contain only one element. Each element is going to be an encoded
        list of spans.
        """
        return self.output


def generate_app_main(settings, firehose=False):
    normal_transport = MockTransport()
    firehose_transport = MockTransport()
    app_main = main({}, **settings)
    app_main.registry.settings['zipkin.transport_handler'] = normal_transport
    if firehose:
        app_main.registry.settings['zipkin.firehose_handler'] = firehose_transport
    return app_main, normal_transport, firehose_transport
