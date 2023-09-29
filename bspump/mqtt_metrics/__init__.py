import paho.mqtt.client as mqtt
import time
import json
import logging
from asab.web.rest.json import JSONDumper
import asab
import re

L = logging.getLogger(__name__)


def parse_topology(pipelines: dict):
    components = []
    metrics_components = []
    for pipeline in pipelines.values():
        components.append(pipeline["Sources"][0])
        # get metrics
        for metric in pipeline["Metrics"]:
            if (
                metric["type"] == "Counter"
                and metric["name"] == "bspump.pipeline.eps_processor"
            ):
                metrics_components.append(metric)
        for processor in pipeline["Processors"][0]:
            components.append(processor)

    output_list = []
    for i in range(len(components)):
        current_dict = {"id": components[i]["Id"]}

        # If it's not the last element, add the "wires" key
        if i < len(components) - 1:
            current_dict["wires"] = [components[i + 1]["Id"]]
        else:
            current_dict["wires"] = []
        for metric in metrics_components:
            if metric["static_tags"]["processor"] == current_dict["id"]:
                current_dict["metrics"] = {
                    "eps.in": metric["fieldset"][0]["values"]["eps.in"],
                    "eps.out": metric["fieldset"][0]["values"]["eps.out"],
                }
                break

        output_list.append(current_dict)

    # add metrics to the source as it doesn't have any metrics from the metric service
    if "metrics" not in output_list[0]:
        if "eps.out" in output_list[1]["metrics"]:
            output_list[0]["metrics"] = {}
            output_list[0]["metrics"]["eps.out"] = int(output_list[1]["metrics"]["eps.out"])

    output = {"topology": output_list}
    return output


class MQTTService(asab.Service):
    def __init__(self, app, service_name="bspump.MQTTService"):
        super().__init__(app, service_name)
        self.App = app
        broker = asab.Config["MQTTMetrics"].get("broker")
        self.host, self.port = broker.split(":")
        self.client = mqtt.Client()

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(self.host, int(self.port), 60)
        self.client.loop_start()

        self.dumper = JSONDumper(pretty=False)
        self.container_id = None

        self.sub_queue = []

    def on_message(self, client, userdata, message):
        payload = message.payload.decode("utf-8")
        svc = self.App.get_service("bspump.PumpService")
        topic = message.topic

        # Regex patterns
        topology_pattern = r"^c/(?P<container_identifier>[^/]+)/topology/get$"
        events_pattern = r"^c/(?P<container_identifier>[^/]+)/c/(?P<pipeline_identifier>[^/]+)/c/(?P<component_identifier>[^/]+)/events/subscribe$"

        # Matching
        topology = re.match(topology_pattern, topic)
        events = re.match(events_pattern, topic)

        if topology:
            if payload == "get":
                pump_topology = parse_topology(json.loads(self.dumper(svc.Pipelines)))
                client.publish(f"c/{self.container_id}/topology", json.dumps(pump_topology))
        
        if events:
            try:
                payload = json.loads(payload)
            except json.decoder.JSONDecodeError:
                payload = message.payload.decode("utf-8")
                L.warning("Payload is not a valid JSON. Payload: {}".format(payload))
                return
            
            pipeline = events.group("pipeline_identifier")
            processor = events.group("component_identifier")
            pipeline = svc.locate(f"{pipeline}")

            num_of_events = payload["event_count"]

            if num_of_events is not None and num_of_events > 0:
                source = pipeline.locate_source(f"{processor}")
                if source is not None:
                    source.EventsToPublish = num_of_events
                else:
                    L.warning(f"adding {processor} to {pipeline.Id}")
                    pipeline.PublishingProcessors[processor] = num_of_events

    # Callback when connected to the MQTT broker
    def on_connect(self, client, userdata, flags, rc):
        # wait for /container_id file to exist and read it
        while True:
            try:
                with open("/container_id", "r") as f:
                    self.container_id = f.read().replace("\n", "")
                    break
            except FileNotFoundError:
                time.sleep(1)
        client.subscribe(f"c/{self.container_id}/topology/get")

        for sub in self.sub_queue:
            client.subscribe(f"c/{self.container_id}/{sub}")

    def subscribe(self, pipeline, component):
        self.sub_queue.append(f"c/{pipeline}/c/{component}/events/subscribe")

    def publish(self, pipeline, component, event):
        data = {
            "timestamp": time.time_ns(),
            "data": event,
            "event_number": component.EventCount,
        }
        self.client.publish(
            f"c/{self.container_id}/c/{pipeline}/c/{component.Id}/events",
            json.dumps(data),
        )
