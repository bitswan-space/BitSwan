import paho.mqtt.client as mqtt
import time
import json
import logging
from asab.web.rest.json import JSONDumper
import asab
import re
import asab

L = logging.getLogger(__name__)


def get_pipeline_topology(pipelines: dict, pipeline):
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
    for processor in pipeline_data["Processors"][0]:
        components.append(processor)

    output = {
        "topology": {},
        "display-style": "graph",
        "display-priority": "shown",
    }
    for i in range(len(components)):
        component_data = {}

        # If it's not the last element, add the "wires" key
        if i < len(components) - 1:
            component_data["wires"] = [components[i + 1]["Id"]]
        else:
            component_data["wires"] = []

        # Implement getting properties
        component_data["properties"] = {}
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
            output["topology"][components[0]["Id"]]["metrics"]["eps.out"] = int(output["topology"][components[1]["Id"]]["metrics"]["eps.out"])

    return output

def get_pipelines(pipelines: dict):
    output = {
        "topology" : {},
        "display-style": "graph",
        "display-priority": "hidden"
    }
    for pipeline in pipelines.values():
        pipeline_dict = {
            "wires": [],
            "properties": [],
            "metrics": [],
            "capabilities": ["has-children"],
        }
        output["topology"][pipeline["Id"]] = pipeline_dict

    return output


class MQTTService(asab.Service):
    def __init__(self, app, service_name="bspump.MQTTService"):
        super().__init__(app, service_name)
        self.App = app
        broker = asab.Config["MQTTMetrics"].get("broker")
        self.host, self.port = broker.split(":")
        self.client = mqtt.Client()
        self.dumper = JSONDumper(pretty=False)

        self.sub_queue = []

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(self.host, int(self.port), 60)
        self.client.loop_start()
        self.connected = False

        self.dumper = JSONDumper(pretty=False)


    def on_message(self, client, userdata, message):
        payload = message.payload.decode("utf-8")
        svc = self.App.get_service("bspump.PumpService")
        topic = message.topic


        # Regex patterns
        pipelines_list_pattern = r"^c/(?P<deployment_identifier>[^/]+)/topology/get$"
        pipeline_components_pattern = r"^c/(?P<deployment_identifier>[^/]+)/c/(?P<pipeline_identifier>[^/]+)/topology/get$"
        events_pattern = r"^c/(?P<deployment_identifier>[^/]+)/c/(?P<pipeline_identifier>[^/]+)/c/(?P<component_identifier>[^/]+)/events/subscribe$"

        # Matching
        pipelines_list = re.match(pipelines_list_pattern, topic)
        pipeline_components = re.match(pipeline_components_pattern, topic)
        events = re.match(events_pattern, topic)

        # Get list of pipelines from application
        if pipelines_list:
            try:
                payload = json.loads(payload)
            except json.decoder.JSONDecodeError:
                payload = message.payload.decode("utf-8")
                L.warning(f"Payload sent to {topic} is not a valid JSON. Payload: {payload}")
                return

            method = payload.get("method")
            if method is not None and method == "get":
                pump_topology = get_pipelines(json.loads(self.dumper(svc.Pipelines)))
                client.publish(f"c/{self.App.HostName}/topology", json.dumps(pump_topology))

        # Get components of one pipeline
        if pipeline_components:
            try:
                payload = json.loads(payload)
            except json.decoder.JSONDecodeError:
                payload = message.payload.decode("utf-8")
                L.warning(f"Payload sent to {topic} is not a valid JSON. Payload: {payload}")
                return
            
            method = payload.get("method")
            if method is not None and method == "get":
                pipeline = pipeline_components.group("pipeline_identifier")
                pipeline_topology = get_pipeline_topology(json.loads(self.dumper(svc.Pipelines)), pipeline)
                client.publish(f"c/{self.App.HostName}/c/{pipeline}/topology", json.dumps(pipeline_topology))

        if events:
            try:
                payload = json.loads(payload)
            except json.decoder.JSONDecodeError:
                payload = message.payload.decode("utf-8")
                L.warning(f"Payload sent to {topic} is not a valid JSON. Payload: {payload}")
                return

            pipeline = events.group("pipeline_identifier")
            processor = events.group("component_identifier")
            pipeline = svc.locate(f"{pipeline}")

            num_of_events = payload.get("event_count")

            if num_of_events is not None and num_of_events > 0:
                source = pipeline.locate_source(f"{processor}")
                if source is not None:
                    source.EventsToPublish = num_of_events
                else:
                    L.info(f"adding {processor} to {pipeline.Id}")
                    pipeline.PublishingProcessors[processor] = num_of_events

    # Callback when connected to the MQTT broker
    def on_connect(self, client, userdata, flags, rc):
        self.apply_subscriptions()
        self.connected = True

    def apply_subscriptions(self):
        self.client.subscribe(f"c/{self.App.HostName}/topology/get")

        for sub in self.sub_queue:
            self.client.subscribe(f"c/{self.App.HostName}/{sub}")

    def add_pipeline(self, pipeline):
        self.sub_queue.append(f"c/{pipeline}/topology/get")
        if self.connected:
            self.apply_subscriptions()

    def subscribe(self, pipeline, component):
        self.sub_queue.append(f"c/{pipeline}/c/{component}/events/subscribe")
        if self.connected:
            self.apply_subscriptions()

    def publish(self, pipeline, component, event):
        data = {
            "timestamp": time.time_ns(),
            "data": event,
            "event_number": component.EventCount,
        }
        self.client.publish(
            f"c/{self.App.HostName}/c/{pipeline}/c/{component.Id}/events",
            json.dumps(data),
        )
