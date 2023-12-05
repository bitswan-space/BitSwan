from functools import partial
import bspump
import copy
import os
from typing import Any, Callable


class AsabObjMocker:
    def __init__(self):
        self.Id = None
        self.Loop = None
        self.items = []

    def inject(self, context, event, depth):
        self.items.append(event)
        return event

    def clear(self):
        self.items = []


class DevEventsStorage:
    def __init__(self):
        self.old_events: dict[str, list[Any]] = {}
        self.events: list[Any] = []

    def set_current_events(self, events: list[Any]) -> None:
        """Sets current events to list passed in

        Args:
            events (list[Any]): list to be set as current events
        """
        self.events = events

    def cycle(self, name: str) -> None:
        """Cycles current events to old events with name as key

        Args:
            name (str): name of the function
        """
        self.old_events[name] = copy.deepcopy(self.events)

    def clear(self) -> None:
        """Resets the state to the initial
        """
        self.old_events = {}
        self.events = []

    def print_events(self):
        for event in self.events:
            print(event)

    def update_current_events(self, curr_name: str) -> None:
        for name, events in self.old_events.items():
            if name == curr_name:
                self.set_current_events(events)
    
    def step(self, name: str, func: Callable) -> None:
        self.update_current_events(name)
        self.cycle(name)
        self.set_current_events([func(event) for event in self.events])
        self.print_events()


def is_running_in_jupyter():
    try:
        from IPython import get_ipython

        # Check if the IPython kernel is running which is a strong indication of a Jupyter environment
        if "IPKernelApp" in get_ipython().config:
            return True
        if (
            "VSCODE_PID" in os.environ
        ):  # Check for Visual Studio Code's Jupyter extension
            return True
        return False
    except Exception:
        return False


__bitswan_processors = []
__bitswan_pipelines = {}
__bitswan_dev = is_running_in_jupyter()
__bitswan_current_pipeline = None
__bitswan_dev_events = DevEventsStorage()
__bitswan_connections = []
__bitswan_lookups = []
__bitswan_app_post_inits = []


def test_events(events):
    global __bitswan_dev_events
    __bitswan_dev_events.set_current_events(events)


def register_app_post_init(func):
    """
    Ex:
    @register_app_post_init
    def post_init(app):
        app.PubSub.subscribe("Application.tick!", app.tick)
    """
    global __bitswan_app_post_inits
    __bitswan_app_post_inits.append(func)

def register_connection(func):
    """
    Ex:
    @register_connection
    def connection(app):
        return bspump.kafka.KafkaConnection(app, "KafkaConnection")
    """
    global __bitswan_connections
    __bitswan_connections.append(func)


def register_lookup(func):
    """
    Ex:
    @register_lookup
    def lookup(app):
      return ENodeBLookup(app, id='ENodeBLookup')
    """
    global __bitswan_lookups
    __bitswan_lookups.append(func)


def new_pipeline(name):
    global __bitswan_processors
    global __bitswan_current_pipeline
    __bitswan_processors = []
    __bitswan_current_pipeline = name


def end_pipeline():
    global __bitswan_current_pipeline
    global __bitswan_processors
    global __bitswan_pipelines
    global __bitswan_dev

    if __bitswan_dev:
        return

    # Capture the current state of __bitswan_processors
    current_processors = list(__bitswan_processors)

    class Pipeline(bspump.Pipeline):
        def __init__(self, app, pipeline_id):
            super().__init__(app, pipeline_id)
            processors = []
            for processor in current_processors:
                instance = processor(app, self)
                processors.append(instance)
            self.build(*processors)

    # Append the new Pipeline class
    __bitswan_pipelines[__bitswan_current_pipeline] = Pipeline


def register_source(func):
    """
    Ex:
    @register_source
    def source(app, pipeline):
        return bspump.socket.TCPStreamSource(app, pipeline)
    """
    global __bitswan_processors
    __bitswan_processors.append(func)


def register_processor(func):
    """
    Ex:
    @register_processor
    def processor(app, pipeline):
        return bspump.socket.TCPStreamProcessor(app, pipeline)
    """
    global __bitswan_processors
    global __bitswan_dev
    global __bitswan_dev_events
    if not __bitswan_dev:
        __bitswan_processors.append(func)
    else:
        processor = func(AsabObjMocker(), AsabObjMocker())

        callable_process = partial(processor.process, None)
        __bitswan_dev_events.step(func.__name__, callable_process)


def register_generator(func):
    """
    Ex:
    @register_source
    def source(app, pipeline):
        return MyGeneratorClass(app, pipeline)
    """

    async def _fn():
        global __bitswan_processors
        global __bitswan_dev
        global __bitswan_dev_events
        if not __bitswan_dev:
            # TODO: check this
            __bitswan_processors.append(func)
        else:
            app, pipeline = AsabObjMocker(), AsabObjMocker()
            generator = func(app, pipeline)

            __bitswan_dev_events.update_current_events(func.__name__)

            __bitswan_dev_events.cycle(func.__name__)
            __bitswan_dev_new_events = []
            for event in __bitswan_dev_events.events:
                await generator.generate(None, event, 0)
                __bitswan_dev_new_events.extend(pipeline.items)
                pipeline.clear()

            __bitswan_dev_events.set_current_events(__bitswan_dev_new_events)

            __bitswan_dev_events.print_events()

        return func

    def wrapper(*args, **kwargs):
        import asyncio
        import nest_asyncio
        nest_asyncio.apply()
        loop = asyncio.get_event_loop()
        task = asyncio.ensure_future(_fn())
        loop.run_until_complete(task)

    wrapper()
    return _fn


def register_sink(func):
    """
    Ex:
    @register_sink
    def sink(app, pipeline):
        return bspump.socket.TCPStreamSink(app, pipeline)
    """
    global __bitswan_processors
    __bitswan_processors.append(func)


def snake_to_camel_case(name):
    """Convert snake_case name to CamelCase."""
    return ''.join(word.capitalize() for word in name.split('_'))


def step(func):
    global __bitswan_processors
    global __bitswan_dev
    global __bitswan_dev_events
    if not __bitswan_dev:
        # Convert function name from snake case to CamelCase and create a unique class name
        class_name = snake_to_camel_case(func.__name__) + 'Processor'

        # Dynamically create a new Processor class with the custom class name
        CustomProcessor = type(
            class_name,
            (bspump.Processor,),
            {'process': lambda self, context, event: func(event)}
        )

        # Append the new Processor to the __bitswan_processors list
        __bitswan_processors.append(CustomProcessor)
    else:
        __bitswan_dev_events.step(func.__name__, func)


    # Return the original function unmodified
    return func


def _init_pipelines(app, service):
    global __bitswan_pipelines
    for name, pipeline in __bitswan_pipelines.items():
        service.add_pipeline(pipeline(app, name))


def _init_connections(app, service):
    global __bitswan_connections
    for connection in __bitswan_connections:
        service.add_connection(connection(app))


def _init_lookups(app, service):
    global __bitswan_lookups
    for lookup in __bitswan_lookups:
        service.add_lookup(lookup(app))


class App(bspump.BSPumpApplication):
    def __init__(self):
        super().__init__()
        global __bitswan_app_post_inits
        svc = self.get_service("bspump.PumpService")
        _init_connections(self, svc)
        _init_lookups(self, svc)
        _init_pipelines(self, svc)
        for func in __bitswan_app_post_inits:
            func(self)
