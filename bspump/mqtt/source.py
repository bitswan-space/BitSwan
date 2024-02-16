import logging

from ..abc.source import Source

L = logging.getLogger(__name__)

class MQTTSource(Source):
    ConfigDefaults = {
        "topic": "#",
        "qos": 0
    }

    def __init__(self, app, pipeline, connection, id=None, config=None):
        super().__init__(app, pipeline, id=id, config=config)

        self.Connection = pipeline.locate_connection(app, connection)
        self.Connection.subscribe_topic(self.Config["topic"], self.Config["qos"])
        self.Connection.register_handler(self.Config["topic"], self.on_message)

        self._queue = []

    async def main(self):
        while True:
            if len(self._queue) > 0:
                await self.Pipeline.ready()
                await self.process(self._queue.pop(0))

    def on_message(self, client, userdata, message):
        self._queue.append(message.payload)

    