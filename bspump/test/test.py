from ..abc.source import Source
from ..abc.sink import Sink

import copy


class TestSource(Source):
    def __init__(self, *args, **kwargs):
        kwargs["test_events"] = kwargs.get("test_events", {})
        self.test_events = kwargs["test_events"]
        del kwargs["test_events"]
        super().__init__(*args, **kwargs)

    async def main(self):
        import bspump.jupyter

        print(f"\nRunning tests for pipeline {self.Pipeline.Id}.")
        for event, tests in self.test_events.items():
            await self.Pipeline.ready()
            tests["outputs"] = []
            tests["input"] = str(event)
            bspump.jupyter.bitswan_test_probes.clear()
            bspump.jupyter.bitswan_test_probes.update(tests.get("probes", {}))
            print(f"\n    ┌ Testing event:        {event}")
            await self.process(event, context=tests)
            print(f"    └ Outputs:              {tests['outputs']}", end="")
            if tests.get("expect") and tests["outputs"] != tests["expect"]:
                print(" \033[91m✘\033[0m")
                print(f"    ! \033[91mTest failed\033[0m Expected: {tests['expect']}\n")
                exit(1)
            if tests.get("inspect"):
                inspected = tests["inspect"][0](tests["outputs"])
                expected = tests["inspect"][1]
                if not inspected == expected:
                    print(" \033[91m✘\033[0m")
                    print(
                        f"    ! \033[91mInspect failed. Got {inspected} expected {expected}\033[0m"
                    )
                    exit(1)
            print(" \033[92m✔\033[0m")
        print(f"\n\033[92mAll tests passed for {self.Pipeline.Id}.\033[0m\n")
        bspump.jupyter.bitswan_tested_pipelines.add(self.Pipeline.Id)
        if bspump.jupyter.bitswan_tested_pipelines == set(
            self.Pipeline.App.PumpService.Pipelines
        ):
            exit()


class TestSink(Sink):
    def process(self, context, event):
        context["outputs"].append(copy.deepcopy(event))
