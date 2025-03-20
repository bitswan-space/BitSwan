from .processor import ProcessorBase


class Sink(ProcessorBase):
    """
    Sink is basically a processor. It takes an event sends it to a database where it is stored.

    |

    """

    def handle_error(self, context, event, exception, timestamp):
        raise exception

    def _handle_error(self, context, event, exception, timestamp):
        self.handle_error(context, event, exception, timestamp)
