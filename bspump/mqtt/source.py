import asyncio
import logging

from ..abc.source import Source

L = logging.getLogger(__name__)


class MQTTSource(Source):
    ConfigDefaults = {"topic": "#", "qos": 0}

    def __init__(self, app, pipeline, connection, id=None, config=None):
        super().__init__(app, pipeline, id=id, config=config)

        self.Connection = pipeline.locate_connection(app, connection)
        self.Connection.subscribe_topic(self.Config["topic"], self.Config["qos"])
        self.Connection.register_handler(self.Config["topic"], self.on_message)

        self._queue = asyncio.Queue()

    async def main(self):
        try:
            while True:
                await self.Pipeline.ready()
                event = await self._queue.get()
                await self.process(event)
        except asyncio.CancelledError:
            pass

        except BaseException as e:
            L.exception("Error when processing message.")
            self.Pipeline.set_error(None, None, e)

    def on_message(self, client, userdata, message):
        self._queue.put_nowait(message.payload)
