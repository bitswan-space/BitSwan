#!/usr/bin/env python3
import logging
import time

import bspump
import bspump.common
import bspump.elasticsearch
import bspump.file
import bspump.trigger

###

L = logging.getLogger(__name__)

###


class LoadSource(bspump.TriggerSource):
    def __init__(self, app, pipeline, choice=None, id=None, config=None):
        super().__init__(app, pipeline, id=id, config=config)
        self.Number = 200000

    async def cycle(self):
        print("START ----")
        stime = time.time()
        for i in range(0, self.Number):
            event = {"name": "Chuck Norris"}
            await self.process(event)
        etime = time.time()
        print("EPS: {:.0f}".format(self.Number / (etime - stime)))


class SamplePipeline(bspump.Pipeline):
    def __init__(self, app, pipeline_id):
        super().__init__(app, pipeline_id)
        self.build(
            LoadSource(app, self).on(
                bspump.trigger.OpportunisticTrigger(app, chilldown_period=10)
            ),
            bspump.elasticsearch.ElasticSearchSink(app, self, "ESConnection"),
        )


if __name__ == "__main__":
    app = bspump.BSPumpApplication()

    svc = app.get_service("bspump.PumpService")

    svc.add_connection(
        bspump.elasticsearch.ElasticSearchConnection(app, "ESConnection", config={})
    )

    # Construct and register Pipeline
    pl = SamplePipeline(app, "SamplePipeline")
    svc.add_pipeline(pl)

    app.run()
