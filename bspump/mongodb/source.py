""" Module for connecting to Mongo database"""

import asyncio
import logging
from bspump.abc.source import TriggerSource

#

L = logging.getLogger(__name__)


#


class MongoDBSource(TriggerSource):
    """MongoDB database source"""

    ConfigDefaults = {
        "output_queue_max_size": 2,
        "database": "",
        "collection": "",
    }

    def __init__(
        self, app, pipeline, connection, query_parms=None, id=None, config=None
    ):
        """
        Create new instance
                Parameters:
                        app (Application): application
                        pipeline (PipeLone): pipeline
                        connection (Connection): Connection to the database
                        query_parms (Dictionary): Query parameters (filter,projection,number of records)
                        id (int): Id
                        config (Dictionary): Connection configuration
        """

        super().__init__(app, pipeline, id=id, config=config)

        self.Pipeline = pipeline
        self._output_queue = asyncio.Queue()
        self._output_queue_max_size = int(self.Config["output_queue_max_size"])
        self.QueryParms = query_parms
        self.Connection = pipeline.locate_connection(app, connection)
        self.Database = self.Config["database"]
        self.Collection = self.Config["collection"]

    async def cycle(self):
        db = self.Connection.Client[self.Database]

        # We check the queue size and remove throttling if the size is smaller than its defined max size.
        if self._output_queue.qsize() == self._output_queue_max_size - 1:
            self.Pipeline.throttle(self, False)

        coll = db[self.Collection]
        await self.Pipeline.ready()

        # query parms
        q_filter = self.QueryParms.get("filter", None)
        q_projection = self.QueryParms.get("projection", None)
        q_limit = self.QueryParms.get("limit", 0)

        cur = coll.find(q_filter, q_projection, 0, int(q_limit))

        async for recs in cur:
            pass
            await self.process(recs, context={})
