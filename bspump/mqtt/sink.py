import logging

from ..abc.sink import Sink

L = logging.getLogger(__name__)


class MQTTSink(Sink):
    ConfigDefaults = {"topic": "default", "qos": 0, "retain": False}

    def __init__(self, app, pipeline, connection, id=None, config=None):
        super().__init__(app, pipeline, id=id, config=config)

        self.Connection = pipeline.locate_connection(app, connection)

    def process(self, context, event):
        self.Connection.publish_to_topic(
            self.Config["topic"], event, self.Config["qos"], self.Config["retain"]
        )
