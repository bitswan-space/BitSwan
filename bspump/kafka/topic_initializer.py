import json
import yaml
import logging
import typing

import confluent_kafka.admin

import bspump.asab as asab
import bspump
import bspump.abc.sink
import bspump.abc.source


#

L = logging.getLogger(__name__)

#

_TOPIC_CONFIG_OPTIONS = {
    "compression.type",
    "leader.replication.throttled.replicas",
    "message.downconversion.enable",
    "min.insync.replicas",
    "segment.jitter.ms",
    "cleanup.policy",
    "flush.ms",
    "follower.replication.throttled.replicas",
    "segment.bytes",
    "retention.ms",
    "flush.messages",
    "message.format.version",
    "max.compaction.lag.ms",
    "file.delete.delay.ms",
    "max.message.bytes",
    "min.compaction.lag.ms",
    "message.timestamp.type",
    "preallocate",
    "min.cleanable.dirty.ratio",
    "index.interval.bytes",
    "unclean.leader.election.enable",
    "retention.bytes",
    "delete.retention.ms",
    "segment.ms",
    "message.timestamp.difference.max.ms",
    "segment.index.bytes",
}


def _is_kafka_component(component):
    if isinstance(component, bspump.kafka.KafkaSource) or isinstance(
        component, bspump.kafka.KafkaSink
    ):
        return True
    return False


class KafkaTopicInitializer(asab.Configurable):
    """
    KafkaTopicInitializer reads topic configs from file or from Kafka sink/source configs,
    checks if they exists and creates them if they don't.

    KafkaAdminClient requires blocking connection, which is why this class doesn't use
    the connection module from BSPump.

    Usage:
    topic_initializer = KafkaTopicInitializer(app, "KafkaConnection")
    topic_initializer.include_topics(MyPipeline)
    topic_initializer.initialize_topics()
    """

    ConfigDefaults = {
        "client_id": "bspump-topic-initializer",
        "topics_file": "",
        "num_partitions_default": 1,
        "replication_factor_default": 1,
    }

    def __init__(
        self, app, connection, id: typing.Optional[str] = None, config: dict = None
    ):
        """
        Initializes the parameters passed to the class.

        **Parameters**

        app : Application
                Name of the `Application <https://asab.readthedocs.io/en/latest/asab/application.html#>`_.

        connection : Connection
                Information needed to create a connection.

        id: typing.Optional[str] = None :

        config: dict = None : JSON
                configuration file containing important information.

        """
        _id = id if id is not None else self.__class__.__name__
        super().__init__(_id, config)

        # Keeps the topic objects that need to be checked/initialized
        self.RequiredTopics = {}

        # Caches the names of existing topics
        self.ExistingTopics: typing.Optional[set] = None

        self.BootstrapServers = None
        self.ClientId = self.Config.get("client_id")

        self._get_bootstrap_servers(app, connection)

        topics_file = self.Config.get("topics_file")
        if len(topics_file) != 0:
            self.include_topics_from_file(topics_file)

    def _get_bootstrap_servers(self, app, connection):
        svc = app.get_service("bspump.PumpService")
        self.BootstrapServers = (
            svc.Connections[connection].Config["bootstrap_servers"].strip()
        )

    def include_topics(
        self,
        *,
        topic_config=None,
        kafka_component=None,
        pipeline=None,
        config_file=None
    ):
        """
        Includes topic from config file or dict object. It can also scan Pipeline and get topics from Source or Sink.

        **Parameters**

        * :

        topic_config : , default= None
                Topic config file.

        kafka_component : , default= None

        pipeline : , default= None
                Name of the Pipeline.

        config_file : , default= None
                Configuration file.

        """
        # Include topic from config or dict object
        if topic_config is not None:
            L.info("Including topics from dictionary")
            self.include_topics_from_config(topic_config)

        # Include topic from config file
        if config_file is not None:
            L.info("Including topics from '{}'".format(config_file))
            self.include_topics_from_file(config_file)

        # Get topics from Kafka Source or Sink
        if kafka_component is not None:
            L.info("Including topics from {}".format(kafka_component.Id))
            self.include_topics_from_config(kafka_component.Config)

        # Scan the pipeline for KafkaSource(s) or KafkaSink
        if pipeline is not None:
            for source in pipeline.Sources:
                if _is_kafka_component(source):
                    L.info("Including topics from {}".format(source.Id))
                    self.include_topics_from_config(source.Config)
            sink = pipeline.Processors[0][-1]
            if _is_kafka_component(sink):
                L.info("Including topics from {}".format(sink.Id))
                self.include_topics_from_config(sink.Config)

    def include_topics_from_file(self, topics_file: str):
        """
        Includes topics from a topic file.

        **Parameters**

        topics_file:str : str
                Name of a topic file we wanted to include.

        """
        # Support yaml and json input
        ext = topics_file.strip().split(".")[-1].lower()
        if ext == "json":
            with open(topics_file, "r") as f:
                data = json.load(f)
        elif ext in ("yml", "yaml"):
            with open(topics_file, "r") as f:
                data = yaml.safe_load(f)
        else:
            L.warning("Unsupported extension: '{}'".format(ext))

        for topic in data:
            if "topic" not in topic and "name" in topic:  # BACK-COMPAT
                L.warning("Topic attribute 'name' is deprecated; use 'topic' instead.")
                topic["topic"] = topic.pop("name")
            if "config" not in topic and "topic_configs" in topic:  # BACK-COMPAT
                L.warning(
                    "Topic attribute 'topic_configs' is deprecated; use 'config' instead."
                )
                topic["config"] = topic.pop("topic_configs")
            if "num_partitions" not in topic:
                topic["num_partitions"] = int(self.Config.get("num_partitions_default"))
            if "replication_factor" not in topic:
                topic["replication_factor"] = int(
                    self.Config.get("replication_factor_default")
                )
            self.RequiredTopics[topic["topic"]] = confluent_kafka.admin.NewTopic(
                **topic
            )

    def include_topics_from_config(self, config_object):
        """
        Includes topics using a config

        **Parameters**

        config_object : JSON
                config object containing information about what topics we want to include.

        """
        # Every kafka topic needs to have: name, num_partitions and replication_factor
        topic_names = config_object.get("topic").split(",")

        if "num_partitions" in config_object:
            num_partitions = int(config_object.pop("num_partitions"))
        else:
            num_partitions = int(self.Config.get("num_partitions_default"))

        if "replication_factor" in config_object:
            replication_factor = int(config_object.pop("replication_factor"))
        else:
            replication_factor = int(self.Config.get("replication_factor_default"))

        # Additional configs are optional
        topic_configs = config_object.pop("config", {})
        for config_option in set(config_object.keys()):
            if config_option in _TOPIC_CONFIG_OPTIONS:
                topic_configs[config_option] = config_object.pop(config_option)

        # Create topic objects
        for name in topic_names:
            self.RequiredTopics[name] = confluent_kafka.admin.NewTopic(
                topic=name,
                num_partitions=num_partitions,
                replication_factor=replication_factor,
                config=topic_configs,
            )

    def fetch_existing_topics(self):
        admin_client = confluent_kafka.admin.AdminClient(
            {"bootstrap.servers": self.BootstrapServers, "client.id": self.ClientId}
        )
        result = admin_client.list_topics()
        if result is None:
            raise RuntimeError("Empty response from list_topics")
        self.ExistingTopics = set(result.topics.keys())

    def check_and_initialize(self):
        """
        Initializes new topics and logs a warning.

        """
        L.warning(
            "`check_and_initialize()` is obsoleted, use `initialize_topics()` instead"
        )
        self.initialize_topics()

    def initialize_topics(self):
        """
        Initializes topics  ??

        """
        if len(self.RequiredTopics) == 0:
            L.info("No Kafka topics were required.")
            return

        # Fetch topics if not cached
        if self.ExistingTopics is None:
            try:
                self.fetch_existing_topics()
            except Exception as e:
                L.error("Failed to fetch Kafka topics: {}".format(e))
                return

        # Filter out the topics that already exist
        missing_topics = [
            topic
            for topic in self.RequiredTopics.values()
            if topic.topic not in self.ExistingTopics
        ]

        if len(missing_topics) == 0:
            L.info("No missing Kafka topics to be initialized.")
            return

        try:
            admin_client = confluent_kafka.admin.AdminClient(
                {"bootstrap.servers": self.BootstrapServers, "client.id": self.ClientId}
            )

            # Create topics
            # TODO: update configs of existing topics using `admin_client.alter_configs()`
            tasks = admin_client.create_topics(missing_topics)
            for topic, task in tasks.items():
                task.result()

            # Update existing topic cache
            self.ExistingTopics.update(self.RequiredTopics.keys())

            L.log(
                asab.LOG_NOTICE,
                "Kafka topics created",
                struct_data={
                    "topics": ", ".join(topic.topic for topic in missing_topics)
                },
            )

        except Exception as e:
            L.error("Kafka topic initialization failed: {}".format(e))
