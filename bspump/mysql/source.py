import logging

import pymysql
import pymysql.cursors
import pymysql.err

import aiomysql.cursors

from ..abc.source import TriggerSource


L = logging.getLogger(__name__)


class MySQLSource(TriggerSource):
    ConfigDefaults = {"query": ""}

    def __init__(self, app, pipeline, connection, id=None, config=None):
        super().__init__(app, pipeline, id=id, config=config)
        self.Loop = app.Loop
        self._connection = pipeline.locate_connection(app, connection)
        self._query = self.Config["query"]
        self.App = app

    async def cycle(self):
        await self._connection.ConnectionEvent.wait()
        try:
            async with self._connection.acquire_connection() as connection:
                async with connection.cursor(aiomysql.cursors.SSCursor) as cur:
                    await cur.execute(self._query)
                    event = {}
                    while True:
                        await self.Pipeline.ready()
                        row = await cur.fetchone()
                        if row is None:
                            break

                        # Transform row to an event object
                        for i, val in enumerate(row):
                            event[cur.description[i][0]] = val

                        # Pass event to the pipeline
                        await self.process(event)
                    await cur.execute("COMMIT;")
        except (
            pymysql.err.InternalError,
            pymysql.err.ProgrammingError,
            pymysql.err.OperationalError,
        ) as e:
            if e.args[0] in self._connection.RetryErrors:
                L.warn(
                    "Recoverable error '{}' occurred in MySQLSource. Retrying.".format(
                        e.args[0]
                    )
                )
            raise e
