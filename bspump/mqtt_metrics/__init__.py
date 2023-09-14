import paho.mqtt.client as mqtt
import time
import json
from datetime import datetime
import logging
from asab.web.rest.json import JSONDumper

L = logging.getLogger(__name__)


def parse_topology(pipelines: dict):

    components = []
    for pipeline in pipelines.values():
        components.append(pipeline["Sources"][0])
        for processor in pipeline["Processors"][0]:
            components.append(processor)

    print(components)
    output_list = []
    for i in range(len(components)):
        current_dict = {"id": components[i]["Id"]}

        # If it's not the last element, add the "wires" key
        if i < len(components) - 1:
            current_dict["wires"] = [components[i + 1]["Id"]]
        else:
            current_dict["wires"] = []

        output_list.append(current_dict)

    output = {"topology": output_list}
    return output



container_id = None
# Callback when a message is received
def on_message_factory(app):
    dumper = JSONDumper(pretty=False)

    def on_message(client, userdata, message):
        global container_id
        payload = message.payload.decode("utf-8")
        print(message.topic)

        if payload == "get":
            svc = app.get_service("bspump.PumpService")

            topology = parse_topology(json.loads(dumper(svc.Pipelines)))
            L.warning(f"Publishing to {container_id}/Metrics")
            client.publish(f"{container_id[:20]}/Metrics", json.dumps(topology))
    return on_message


# Callback when connected to the MQTT broker
def on_connect(client, userdata, flags, rc):
    global container_id
    # wait for /container_id file to exist and read it
    while True:
        try:
            with open("/container_id", "r") as f:
                container_id = f.read()
                break
        except FileNotFoundError:
            time.sleep(1)
    # L.warning(f"Subscribing to {container_id}/Metrics/get")
    client.subscribe(f"{container_id[:20]}/Metrics/get")


def initialize_mqtt(app, broker):
    # Initialize MQTT client
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message_factory(app)

    # Connect to MQTT broker
    host, port = broker.split(":")
    client.connect(host, int(port), 60)

    # Loop to keep the connection open
    client.loop_start()
