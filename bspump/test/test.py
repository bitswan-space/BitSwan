from ..abc.source import Source
from ..abc.sink import Sink

import copy


class TestSource(Source):
    def __init__(self, *args, **kwargs):
        kwargs['test_events'] = kwargs.get('test_events', {})
        self.test_events = kwargs['test_events']
        del kwargs['test_events']
        super().__init__(*args, **kwargs)

    async def main(self):
        import bspump.jupyter
        for event, tests in self.test_events.items():
            await self.Pipeline.ready()
            tests["outputs"] = []
            print("Input:", event)
            bspump.jupyter.bitswan_test_probes.clear()
            bspump.jupyter.bitswan_test_probes.update(tests.get("probes", {}))
            await self.process(event, context=tests)
            if tests.get("expect") and tests["outputs"] != tests["expect"]:
                print("Expected:", tests["expect"])
                print("Got:", tests["outputs"])
                print("\033[91mTest failed\033[0m")
                exit(1)
            if tests.get("inspect"):
                inspected = tests["inspect"][0](tests["outputs"])
                expected = tests["inspect"][1]
                if not inspected == expected:
                    print(f"\033[91mInspect failed. Got {inspected} expected {expected}\033[0m")
                    exit(1)
            print("Test passed!")
        # terman escape codes for green
        print("\033[92mAll tests passed\033[0m")
        exit()

class TestSink(Sink):
    def process(self, context, event):
        print("Ouput:", event)
        context["outputs"].append(copy.deepcopy(event))
