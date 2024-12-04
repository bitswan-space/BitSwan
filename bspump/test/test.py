from ..abc.source import Source
from ..abc.sink import Sink

import copy
import asyncio
import bspump.jupyter

import nest_asyncio

nest_asyncio.apply()


class TestSource(Source):
    def __init__(self, *args, **kwargs):
        kwargs["test_events"] = kwargs.get("test_events", {})
        self.test_events = kwargs["test_events"]
        del kwargs["test_events"]
        super().__init__(*args, **kwargs)

    def start(self, loop):
        """
        Starts the :meth:`Pipeline <bspump.Pipeline()>` through the _main method, but if main method is implemented
        it starts the coroutine using main method instead.

        **Parameters**

        loop : ?
                        Contains the coroutines.


        """
        if self.Task is not None:
            return

        async def _main():
            """
            Description:

            :return:
            """
            print(f"\nRunning tests for pipeline {self.Pipeline.Id}.")
            # if test_events is a dict we will iterate over its items
            # if it is a list of tuples we iterate over them
            if isinstance(self.test_events, dict):
                test_events = self.test_events.items()
            else:
                test_events = self.test_events
            for event, tests in test_events:
                tests["outputs"] = []
                tests["input"] = str(event)
                bspump.jupyter.bitswan_test_probes.clear()
                bspump.jupyter.bitswan_test_probes.update(tests.get("probes", {}))
                print(f"\n    ┌ Testing event:        {event}")
                all_tasks_before = asyncio.all_tasks()
                await self.process(event, context=tests)
                all_tasks_after = asyncio.all_tasks()
                other_tasks = [
                    task for task in all_tasks_after if task not in all_tasks_before
                ]

                # Wait for all other tasks to complete
                if other_tasks:
                    await asyncio.wait(other_tasks)
                print(f"    └ Outputs:              {tests['outputs']}", end="")
                if tests.get("expect") and tests["outputs"] != tests["expect"]:
                    print(" \033[91m✘\033[0m")
                    print(
                        f"    ! \033[91mTest failed\033[0m Expected: {tests['expect']}\n"
                    )
                    if not self.Pipeline.App.Watch:
                        exit(1)
                if tests.get("inspect"):
                    inspected = tests["inspect"][0](tests["outputs"])
                    expected = tests["inspect"][1]
                    if not inspected == expected:
                        print(" \033[91m✘\033[0m")
                        print(
                            f"    ! \033[91mInspect failed. Got {inspected} expected {expected}\033[0m"
                        )
                        if not self.Pipeline.App.Watch:
                            exit(1)
                if tests.get("inspect_in"):
                    inspected = tests["inspect_in"][0](tests["outputs"])
                    expected = tests["inspect_in"][1]
                    if expected not in inspected:
                        print(" \033[91m✘\033[0m")
                        print(
                            f'    ! \033[91mInspect failed. Got "{inspected}" expected that to contain "{expected}"\033[0m'
                        )
                        if not self.Pipeline.App.Watch:
                            exit(1)

                print(" \033[92m✔\033[0m")
            print(f"\n\033[92mAll tests passed for {self.Pipeline.Id}.\033[0m\n")
            bspump.jupyter.bitswan_tested_pipelines.add(self.Pipeline.Id)
            if bspump.jupyter.bitswan_tested_pipelines == set(
                self.Pipeline.App.PumpService.Pipelines
            ):
                if not self.Pipeline.App.Watch:
                    exit()

        self.Pipeline._evaluate_ready()
        asyncio.get_event_loop().run_until_complete(_main())


class TestSink(Sink):
    def process(self, context, event):
        context["outputs"].append(copy.deepcopy(event))
