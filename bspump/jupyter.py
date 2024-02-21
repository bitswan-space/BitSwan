from functools import partial
import bspump
import os
from typing import Any


class AsabObjMocker:
    def __init__(self):
        self.Id = None
        self.Loop = None


class DevApp(bspump.BSPumpApplication):
    def __init__(self):
        super().__init__(args=[])


class DevRuntime:
    def __init__(self):
        self.events: list[tuple[str, list[Any]]] = {}
        self.dev_app = DevApp()

    def clear(self, name: str, event: list[Any]) -> None:
        self.events = [(name, event)]

    def get_prev_events(self, name) -> tuple[list[tuple[str, list[Any]]], list[Any]]:
        new_eventss = []
        prev_events = None
        for event in self.events:
            if event[0] == name:
                break
            prev_events = event[1]
            new_eventss.append(event)
        return new_eventss, prev_events

    def step(self, name: str, func) -> None:
        new_eventss, prev_events = self.get_prev_events(name)
        new_events = [func(prev_event) for prev_event in prev_events]
        [print(event) for event in new_events]
        new_eventss.append((name, new_events))
        self.events = new_eventss

    async def async_step(self, name: str, func) -> None:
        new_eventss, prev_events = self.get_prev_events(name)
        new_events = []

        async def inject(event):
            new_events.append(event)

        [await func(inject, prev_event) for prev_event in prev_events]
        [print(event) for event in new_events]
        new_eventss.append((name, new_events))
        self.events = new_eventss


async def test_devruntime():
    test_runtime = DevRuntime()

    def test_func(prev_event):
        return prev_event + 1

    tr = test_runtime
    tr.clear("sample", [1, 2, 3])
    tr.step("step1", test_func)
    tr.step("step2", test_func)
    tr.step("step3", test_func)
    assert tr.events == [
        ("sample", [1, 2, 3]),
        ("step1", [2, 3, 4]),
        ("step2", [3, 4, 5]),
        ("step3", [4, 5, 6]),
    ]

    def test_func1(prev_event):
        return prev_event + 7

    tr.step("step2", test_func1)
    assert tr.events == [
        ("sample", [1, 2, 3]),
        ("step1", [2, 3, 4]),
        ("step2", [9, 10, 11]),
    ]

    async def test_func2(injector, prev_event):
        if prev_event % 2 == 0:
            injector(prev_event + 1)

    await tr.async_step("step3", test_func2)
    assert tr.events == [
        ("sample", [1, 2, 3]),
        ("step1", [2, 3, 4]),
        ("step2", [9, 10, 11]),
        ("step3", [11]),
    ]


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
__bitswan_dev_runtime = DevRuntime()
__bitswan_connections = []
__bitswan_lookups = []
_bitswan_app_post_inits = []


def sample_events(events):
    global __bitswan_dev_runtime
    __bitswan_dev_runtime.clear("__sample", events)


def register_app_post_init(func):
    """
    Ex:
    @register_app_post_init
    def post_init(app):
        app.PubSub.subscribe("Application.tick!", app.tick)
    """
    global _bitswan_app_post_inits 
    _bitswan_app_post_inits.append(func)


def register_connection(func):
    """
    Ex:
    @register_connection
    def connection(app):
        return bspump.kafka.KafkaConnection(app, "KafkaConnection")
    """
    global __bitswan_connections
    global __bitswan_dev_runtime
    __bitswan_connections.append(func)
    if __bitswan_dev:
        global __bitswan_dev_runtime
        connection = func(__bitswan_dev_runtime.dev_app)
        __bitswan_dev_runtime.dev_app.PumpService.add_connection(connection)


def register_lookup(func):
    """
    Ex:
    @register_lookup
    def lookup(app):
      return ENodeBLookup(app, id='ENodeBLookup')
    """
    global __bitswan_lookups
    __bitswan_lookups.append(func)
    if __bitswan_dev:
        global __bitswan_dev_runtime
        lookup = func(__bitswan_dev_runtime.dev_app)
        __bitswan_dev_runtime.dev_app.PumpService.add_lookup(lookup)


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
    global __bitswan_dev_runtime
    if not __bitswan_dev:
        __bitswan_processors.append(func)
    else:
        processor = func(__bitswan_dev_runtime.dev_app, AsabObjMocker())

        callable_process = partial(processor.process, None)
        __bitswan_dev_runtime.step(func.__name__, callable_process)


def register_generator(func):
    """
    Ex:
    @register_generator
    def generator(app, pipeline):
        return MyGeneratorClass(app, pipeline)
    """

    async def _fn():
        global __bitswan_processors
        global __bitswan_dev
        global __bitswan_dev_runtime
        if not __bitswan_dev:
            # TODO: check this
            __bitswan_processors.append(func)
        else:
            app, pipeline = __bitswan_dev_runtime.dev_app, AsabObjMocker()
            generator = func(app, pipeline)

            async def asfunc(inject, event):
                async def super_inject(context, event, depth):
                    return await inject(event)

                pipeline.inject = super_inject
                return await generator.generate(None, event, 0)

            await __bitswan_dev_runtime.async_step(func.__name__, asfunc)

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
    return "".join(word.capitalize() for word in name.split("_"))


def step(func):
    global __bitswan_processors
    global __bitswan_dev
    global __bitswan_dev_runtime
    if not __bitswan_dev:
        # Convert function name from snake case to CamelCase and create a unique class name
        class_name = snake_to_camel_case(func.__name__) + "Processor"

        # Dynamically create a new Processor class with the custom class name
        CustomProcessor = type(
            class_name,
            (bspump.Processor,),
            {"process": lambda self, context, event: func(event)},
        )

        # Append the new Processor to the __bitswan_processors list
        __bitswan_processors.append(CustomProcessor)
    else:
        __bitswan_dev_runtime.step(func.__name__, func)

    # Return the original function unmodified
    return func


def async_step(func):
    # Convert function name from snake case to CamelCase and create a unique class name
    class_name = snake_to_camel_case(func.__name__) + "Generator"

    # Dynamically create a new Generator class with the custom class name
    async def _generate(self, context, event, depth):
        async def injector(event):
            return self.Pipeline.inject(context, event, depth)

        return await func(injector, event)

    CustomGenerator = type(
        class_name,
        (bspump.Generator,),
        # Async generate function calls func with injector and event. The injector is taken from the pipeline.
        {"generate": _generate},
    )

    def generator(app, pipeline):
        return CustomGenerator(app, pipeline)

    generator.__name__ = func.__name__
    register_generator(generator)


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
        global _bitswan_app_post_inits
        svc = self.get_service("bspump.PumpService")
        _init_connections(self, svc)
        _init_lookups(self, svc)
        _init_pipelines(self, svc)
        for func in _bitswan_app_post_inits:
            func(self)
