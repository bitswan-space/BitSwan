from croniter import croniter
from datetime import datetime
from .trigger import Trigger


class CronTrigger(Trigger):
    """
    Trigger that allows to use crontab syntax
    for specifying freqency of script execution
    """

    def __init__(self, app, cron_string, init_time, id=None):
        super().__init__(app, id)
        self.cron_string = cron_string
        self.init_time = init_time
        self.next_trigger_time = self.get_new_time(cron_string, init_time)

        app.PubSub.subscribe("Application.tick!", self.on_timer)

    async def on_timer(self, event_type="simulated"):
        """
        Method that is called on every tick of the application.
        """
        if datetime.now() > self.next_trigger_time:
            # get new time for next trigger
            self.next_trigger_time = self.get_new_time(
                self.cron_string, self.next_trigger_time
            )
            self.fire()
        else:
            return

    def pause(self, pause=True):
        """
        Pauses the trigger
        """
        super().pause(pause)
        if not pause:
            self.Loop.call_soon(self.on_tick)

    def get_new_time(self, cron_string, time):
        """
        Calculates new time for next trigger
        """
        iterable = croniter(cron_string, time)
        return iterable.get_next(datetime)

    @classmethod
    def construct(cls, app, definition: dict):
        id = definition.get("id")
        interval = definition.get("args", {}).get("cron_string")
        if interval is None:
            raise RuntimeError("CronTrigger needs interval to be defined")
        init_time = datetime.now()
        return cls(app, id=id, cron_string=interval, init_time=init_time)
