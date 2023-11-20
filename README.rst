BSPump: A real-time stream processor for Python 3.5+
====================================================

Principles
----------

* Everything is a stream
* Kappa architecture
* Real-Time
* High performance
* Asynchronous via Python 3.5+ ``async``/``await`` and ``asyncio``
* `Event driven Architecture <https://en.wikipedia.org/wiki/Event-driven_architecture>`_ / `Reactor pattern <https://en.wikipedia.org/wiki/Reactor_pattern>`_
* Compatible with `pypy <http://pypy.org>`_, Just-In-Time compiler capable of boosting Python code performace more then 5x times


Stream processor example
------------------------

.. code:: python

    #!/usr/bin/env python3
    import bspump
    import bspump.socket
    import bspump.common
    import bspump.elasticsearch

    class MyPipeline(bspump.Pipeline):
        def __init__(self, app):
            super().__init__(app)
            self.build(
                bspump.socket.TCPStreamSource(app, self),
                bspump.common.JSONParserProcessor(app, self),
                bspump.elasticsearch.ElasticSearchSink(app, self, "ESConnection")
            )


    if __name__ == '__main__':
        app = bspump.BSPumpApplication()
        svc = app.get_service("bspump.PumpService")
        svc.add_connection(bspump.elasticsearch.ElasticSearchConnection(app, "ESConnection"))
        svc.add_pipeline(MyPipeline(app))
        app.run()

You can write stream processors using Jupyter notebook and bind mounting that jupyter notebook into the bitswan-pre docker image at the path ``/opt/pipelines/main.ipynb``. Here is an example docker-compose entry.

.. code:: yaml

  bitswan-pipeline-1:
    restart: always
    image: public.ecr.aws/bitswan/bitswan-pre:sha256_7e88d9274ddd85cc2afecda8f863c57d6ef998478f56dddb3d4ceb13d55804b7
    volumes:
      - ${PWD}/bitswan-pipeline-1/pipelines.conf:/conf/pipelines.conf:ro
      - ${PWD}/bitswan-pipeline-1/main.ipynb:/opt/pipelines/main.ipynb:ro
      - ${PWD}/bitswan-pipeline-1/extra-dependencies.txt:/opt/extra-dependencies:ro


Available technologies
----------------------

* ``bspump.amqp`` AMQP/RabbitMQ connection, source and sink
* ``bspump.avro`` Apache Avro file source and sink
* ``bspump.common`` Common processors and parsers
* ``bspump.elasticsearch`` ElasticSearch connection, source and sink
* ``bspump.file`` File sources and sinks (plain files, JSON, CSV)
* ``bspump.filter`` Content, Attribute and TimeDrift filters
* ``bspump.http.client``  HTTP client source, WebSocket client sink
* ``bspump.http.web`` HTTP server source and sink, WebSocket server source
* ``bspump.influxdb`` InfluxDB connection and sink
* ``bspump.kafka`` Kafka connection, source and sink
* ``bspump.mail`` SMTP connection and sink
* ``bspump.mongodb`` MongoDB connection and lookup
* ``bspump.mysql`` MySQL connection, source and sink
* ``bspump.parquet`` Apache Parquet file sink
* ``bspump.postgresql`` PostgreSQL connection and sink
* ``bspump.slack`` Slack connection and sink
* ``bspump.socket`` TCP source, UDP source
* ``bspump.trigger`` Opportunistic, PubSub and Periodic triggers
* ``bspump.crypto`` Cryptography
* ``bspump.declarative`` Declarative processors and expressions

  * Hashing: SHA224, SHA256, SHA384, SHA512, SHA1, MD5, BLAKE2b, BLAKE2s
  * Symmetric Encryption: AES 128, AES 192, AES 256

* ``bspump.analyzer``

  * Time Window analyzer
  * Session analyzer
  * Geographical analyzer
  * Time Drift analyzer

* ``bspump.lookup``

  * GeoIP Lookup

* ``bspump.unittest``

  * Interface for testing Processors / Pipelines

* ``bspump.web`` Pump API endpoints for pipelines, lookups etc.

Google Sheet with technological compatiblity matrix:
https://docs.google.com/spreadsheets/d/1L1DvSuHuhKUyZ3FEFxqEKNpSoamPH2Z1ZaFuHyageoI/edit?usp=sharing

Licence
-------

Bitswan is open-source software, available under BSD 3-Clause License.

