import bspump.asab
import asyncio
from .trigger import Trigger


class PeriodicTrigger(Trigger):
    def __init__(self, app, interval=None, id=None):
        """
        Interval is in seconds, can be a float or int.
        """

        super().__init__(app, id)
        self.Timer = bspump.asab.Timer(app, self.on_timer, autorestart=True)
        self.Timer.start(interval)

        async def run_on_ready():
            for pipeline in app.PumpService.Pipelines.values():
                while not pipeline.is_ready():
                    await asyncio.sleep(0.1)
            await self.Timer.Handler()

        asyncio.ensure_future(run_on_ready())

    async def on_timer(self):
        self.fire()

    @classmethod
    def construct(cls, app, definition: dict):
        id = definition.get("id")
        interval = definition.get("args", {}).get("interval", 1.0)
        return cls(app, id=id, interval=interval)
