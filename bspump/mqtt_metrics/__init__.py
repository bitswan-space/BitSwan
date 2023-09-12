import paho.mqtt.client as mqtt
import time
import json
from datetime import datetime
from asab.web.rest.json import JSONDumper


container_id = None
# Callback when a message is received
def on_message_factory(app):
    dumper = JSONDumper(pretty=True)
    def on_message(client, userdata, message):
        global container_id
        payload = message.payload.decode("utf-8")
        print(message.topic)

        if payload == "get":
            svc = app.get_service("bspump.PumpService")
            metrics_and_topology = dumper(svc.Pipelines)

            client.publish(f"{container_id}/Metrics", json.dumps(metrics_and_topology))
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
    client.subscribe(f"{container_id}/Metrics/get")

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
