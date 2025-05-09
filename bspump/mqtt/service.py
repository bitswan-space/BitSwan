import re
import json
import logging
import time
from bspump.asab import Service, Config
from bspump.asab.web.rest.json import JSONDumper

L = logging.getLogger(__name__)


def get_pipeline_topology(pump, pipeline):
    dumper = JSONDumper(pretty=False)
    pipelines = json.loads(dumper(pump.Pipelines))

    pipeline_obj = pump.Pipelines[pipeline]

    pipeline_data = pipelines[pipeline]
    components = []
    metrics_components = []
    components.append(pipeline_data["Sources"][0])
    # get metrics
    for metric in pipeline_data["Metrics"]:
        if (
            metric["type"] == "Counter"
            and metric["name"] == "bspump.pipeline.eps_processor"
        ):
            metrics_components.append(metric)
    for depth in pipeline_data["Processors"]:
        for component in depth:
            components.append(component)

    output = {
        "topology": {},
        "display-style": "graph",
        "display-priority": "shown",
    }
    for i in range(len(components)):
        component_data = {}

        component_obj = pipeline_obj.locate_source(components[i]["Id"])
        if component_obj is None:
            component_obj = pipeline_obj.locate_processor(components[i]["Id"])

        # If it's not the last element, add the "wires" key
        if i < len(components) - 1:
            component_data["wires"] = [components[i + 1]["Id"]]
        else:
            component_data["wires"] = []

        # Implement getting properties
        component_data["properties"] = {
            key: value for key, value in component_obj.Config.items()
        }
        component_data["capabilities"] = ["subscribable-events"]

        for metric in metrics_components:
            if metric["static_tags"]["processor"] == components[i]["Id"]:
                component_data["metrics"] = {
                    "eps.in": metric["fieldset"][0]["values"]["eps.in"],
                    "eps.out": metric["fieldset"][0]["values"]["eps.out"],
                }
                break
        output["topology"][components[i]["Id"]] = component_data

    # add metrics to the source as it doesn't have any metrics from the metric service
    if "metrics" not in output["topology"][components[0]["Id"]]:
        if "eps.out" in output["topology"][components[1]["Id"]]["metrics"]:
            output["topology"][components[0]["Id"]]["metrics"] = {}
            output["topology"][components[0]["Id"]]["metrics"]["eps.out"] = int(
                output["topology"][components[1]["Id"]]["metrics"]["eps.out"]
            )

    message = get_message_structure()
    message["data"] = output
    message["count"] = 1
    message["remaining_subscription_count"] = 1

    return message


def get_pipelines(pipelines: dict):
    output = {"topology": {}, "display-style": "graph", "display-priority": "hidden"}
    for pipeline in pipelines.values():
        pipeline_dict = {
            "wires": [],
            "properties": [],
            "metrics": [],
            "capabilities": ["has-children"],
        }
        output["topology"][pipeline.Id] = pipeline_dict

    message = get_message_structure()
    message["data"] = output
    message["count"] = 1
    message["remaining_subscription_count"] = 1

    return message


def get_message_structure():
    return {
        "timestamp": time.time_ns(),
        "data": {},
        "count": 0,
        "remaining_subscription_count": 0,
    }


class MQTTService(Service):
    def __init__(self, app, service_name="bspump.MQTTService", connection=None):
        super().__init__(app, service_name)
        self.App = app
        self.dumper = JSONDumper(pretty=False)
        self.Connection = None
        self.ConnectionId = connection
        try:
            self.max_count = int(Config["mqtt"].get("max_count"))
        except Exception:
            L.warning(
                "MQTTService: The max_count parameter is not set in the configuration file or is not an integer. Default value is 100."
            )
            self.max_count = 100

    def components_initialize(self):
        svc = self.App.get_service("bspump.PumpService")
        self.Connection = svc.locate_connection(self.ConnectionId)

        for pipeline in svc.Pipelines.values():
            self.Connection.publish_to_topic(
                f"/c/{pipeline.Id}/topology",
                json.dumps(get_pipeline_topology(svc, pipeline.Id)),
                retain=True,
            )

            for depth in pipeline.Processors:
                for component in depth:
                    pipeline.PublishingProcessors[component.Id] = 0
                    self.Connection.subscribe_topic(
                        f"/c/{pipeline.Id}/c/{component.Id}/events/subscribe"
                    )
                    self.Connection.register_handler(
                        f"/c/{pipeline.Id}/c/{component.Id}/events/subscribe",
                        self.on_message,
                    )

            for source in pipeline.Sources:
                self.Connection.subscribe_topic(
                    f"/c/{pipeline.Id}/c/{source.Id}/events/subscribe"
                )
                self.Connection.register_handler(
                    f"/c/{pipeline.Id}/c/{source.Id}/events/subscribe",
                    self.on_message,
                )

        self.Connection.publish_to_topic(
            "/topology",
            json.dumps(get_pipelines(svc.Pipelines)),
            retain=True,
        )

    def on_message(self, client, userdata, message):
        payload = message.payload.decode("utf-8")
        svc = self.App.get_service("bspump.PumpService")
        topic = message.topic

        # Regex patterns
        events_pattern = r"^/c/(?P<pipeline_identifier>[^/]+)/c/(?P<component_identifier>[^/]+)/events/subscribe$"

        # Matching
        events = re.match(events_pattern, topic)

        # Get list of pipelines from application
        try:
            payload = json.loads(payload)
        except json.decoder.JSONDecodeError:
            payload = message.payload.decode("utf-8")
            L.warning(
                f"Payload sent to {topic} is not a valid JSON. Payload: {payload}"
            )
            return

        count = payload.get("count")
        if count is None or count < 0:
            return

        count = min(count, self.max_count)

        if events:
            pipeline = events.group("pipeline_identifier")
            processor = events.group("component_identifier")
            pipeline = svc.locate(f"{pipeline}")

            if pipeline is None:
                L.warning(f"Pipeline {pipeline} not found")
                return

            source = pipeline.locate_source(f"{processor}")
            if source is not None:
                source.EventsToPublish = count
            else:
                processor = pipeline.locate_processor(f"{processor}")

                if processor is None:
                    L.warning(f"Processor {processor} not found")
                    return

                pipeline.PublishingProcessors[processor.Id] = max(
                    count, pipeline.PublishingProcessors[processor.Id]
                )

    def publish_event(self, pipeline, component, event, count_remaining):
        data = get_message_structure()
        if isinstance(event, bytes):
            event = event.decode("utf-8")
        data["data"] = event
        data["count"] = component.EventCount
        data["remaining_subscription_count"] = count_remaining
        self.Connection.publish_to_topic(
            f"/c/{pipeline}/c/{component.Id}/events",
            json.dumps(data, default=lambda x: x.__class__.__name__),
        )
