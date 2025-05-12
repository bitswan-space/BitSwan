import paho.mqtt.client as mqtt
import logging

from ..abc.connection import Connection

L = logging.getLogger(__name__)


class MQTTConnection(Connection):
    ConfigDefaults = {
        "broker": "localhost:1883",
        "keepalive": 60,
        "username": "",
        "password": "",
    }

    def __init__(self, app, id=None, config=None):
        super().__init__(app, id=id, config=config)
        self._client = mqtt.Client(transport="websockets")
        broker = self.Config["broker"]
        self._host, self._port = broker.split(":")

        if self._port == "443":
            # communication between public broker
            self._client.tls_set(cert_reqs=mqtt.ssl.CERT_REQUIRED)
        else:
            # internal communication between broker
            self._client.tls_set(cert_reqs=mqtt.ssl.CERT_NONE)

        if self.Config["username"] != "" and self.Config["password"] != "":
            self._client.username_pw_set(
                self.Config["username"], self.Config["password"]
            )

        self._client.connect(self._host, int(self._port), int(self.Config["keepalive"]))

        self._dispatcher = MQTTMessageDispatcher()

        self._client.on_connect = self.on_connect
        self._client.on_message = self._dispatcher.dispatch
        self.Connected = False
        self._client.loop_start()

    def on_connect(self, client, userdata, flags, rc, properties=None):
        L.info(f"Connected to MQTT broker: {self._host}:{self._port}")
        self.Connected = True

    def register_handler(self, topic, handler):
        self._dispatcher.register(topic, handler)

    def subscribe_topic(self, topic, qos=0):
        self._client.subscribe(topic, qos)

    def publish_to_topic(self, topic, payload, qos=0, retain=False):
        self._client.publish(topic, payload, qos, retain)


class MQTTMessageDispatcher:
    def __init__(self):
        self.handlers = {}

    def register(self, topic, handler):
        self.handlers[topic] = handler

    def dispatch(self, client, userdata, message):
        topic = message.topic
        if topic in self.handlers:
            self.handlers[topic](client, userdata, message)
        else:
            L.warning(f"No handler for topic {topic}")
