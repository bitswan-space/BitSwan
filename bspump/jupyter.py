import bspump
import copy
import os


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
__bitswan_dev_old_events = []
__bitswan_dev_events = []


def test_events(events):
    global __bitswan_dev_events
    __bitswan_dev_events = events


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


def declare_source(func):
    """
    Ex:
    @declare_source
    def source(app, pipeline):
        return bspump.socket.TCPStreamSource(app, pipeline)
    """
    global __bitswan_processors
    __bitswan_processors.append(func)


def declare_processor(func):
    """
    Ex:
    @declare_processor
    def processor(app, pipeline):
        return bspump.socket.TCPStreamProcessor(app, pipeline)
    """
    global __bitswan_processors
    __bitswan_processors.append(func)


def declare_sink(func):
    """
    Ex:
    @declare_sink
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
    global __bitswan_dev_old_events
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
        for name, events in __bitswan_dev_old_events:
            if name == func.__name__:
                __bitswan_dev_events = events
        __bitswan_dev_old_events.append(
            (func.__name__, copy.deepcopy(__bitswan_dev_events))
        )
        __bitswan_dev_events = [func(event) for event in __bitswan_dev_events]
        for event in __bitswan_dev_events:
            print(event)

    # Return the original function unmodified
    return func


def _init_pipelines(app, service):
    global __bitswan_pipelines
    for name, pipeline in __bitswan_pipelines.items():
        service.add_pipeline(pipeline(app, name))


class App(bspump.BSPumpApplication):
    def __init__(self):
        super().__init__()
        svc = self.get_service("bspump.PumpService")
        _init_pipelines(self, svc)
