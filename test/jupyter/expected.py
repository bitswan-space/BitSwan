from bspump.jupyter import *
from bspump.test import TestSink, TestSource
import json
import asyncio


foovar=3


event = {}
test_events = [({"foo":"aaa"},{"expect" : [{"foo": "aaa", "foovar": 3, "barvar": "hello", "bazvar": "aaa"}]}), 
               ({"foo":"aab"},{"expect" : [{"foo": "aab", "foovar": 3, "barvar": "hello", "bazvar": "aab"}]})]


auto_pipeline(
    source=lambda app, pipeline: TestSource(app, pipeline, "TestSource"),
    sink=lambda app, pipeline: TestSink(app, pipeline, "TestSink")
)


@async_step
async def processor_internal(inject, event):
    barvar="hello"
    await asyncio.sleep(0.2)
    my_multiline_string = """a line
non-indented line
    once indented line
        twice indented line
"""
    bazvar=event["foo"]


    print("Next step")
    event["foovar"] = foovar
    event["barvar"] = barvar
    event["bazvar"] = bazvar
    event


    await inject(event)
