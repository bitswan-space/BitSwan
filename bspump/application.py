import logging
import signal
import sys
import os

from bspump.asab import Application, Config
import bspump.asab.web
import bspump.asab.api

from .service import BSPumpService
from .__version__ import __version__, __build__

L = logging.getLogger(__name__)


class BSPumpApplication(Application):
    """
    Description: BSPumpApplication is **class** used for .....

    :return:
    """

    def __init__(self, args=None):
        super().__init__(args=args)

        # Banner
        print("BitSwan BSPump version {}".format(__version__))

        from bspump.asab.proactor import Module

        self.add_module(Module)

        from bspump.asab.metrics import Module

        self.add_module(Module)

        self.ASABApiService = bspump.asab.api.ApiService(self)

        self.PumpService = BSPumpService(self)
        self.WebContainer = None

        from bspump.asab.alert import AlertService

        self.AlertService = AlertService(self)

        self.MQTTService = None

        try:
            # Signals are not available on Windows
            self.Loop.add_signal_handler(signal.SIGUSR1, self._on_signal_usr1)
        except (NotImplementedError, AttributeError):
            pass

        # Register bspump API endpoints, if requested (the web service is present)
        if "web" in Config and Config["web"].get("listen"):
            # Initialize API service
            self.add_module(bspump.asab.web.Module)

            self.WebService = self.get_service("asab.WebService")

            from .web import initialize_web

            self.WebContainer = initialize_web(self.WebService.WebContainer)
            self.ASABApiService.initialize_web()

        mqtt_username = os.environ.get("MQTT_USERNAME")
        mqtt_password = os.environ.get("MQTT_PASSWORD")
        mqtt_broker_url = os.environ.get("MQTT_BROKER_URL")

        if mqtt_broker_url and self.DeploymentId and (mqtt_username or mqtt_password):
            from .mqtt import MQTTService, MQTTConnection

            self.PumpService.add_connection(
                MQTTConnection(
                    self,
                    "MQTTServiceConnection",
                    {
                        "username": mqtt_username,
                        "password": mqtt_password,
                        "broker": mqtt_broker_url,
                    },
                )
            )
            self.MQTTService = MQTTService(self, connection="MQTTServiceConnection")

        # Initialize zookeeper container
        if "zookeeper" in Config.sections():
            from bspump.asab.zookeeper import Module

            self.add_module(Module)

            self.ASABApiService.initialize_zookeeper()

    def create_argument_parser(self):
        """
        Description:

        :return:
        """
        prog = sys.argv[0]
        if prog[-11:] == "__main__.py":
            prog = sys.executable + " -m bspump"

        description = """
BSPump is a stream processor. It is a part of BitSwan.
For more information, visit: https://github.com/LibertyAces/BitSwanPump

version: {}
build: {} [{}]
""".format(
            __version__, __build__, __build__[:7]
        )
        parser = super().create_argument_parser(prog=prog, description=description)
        parser.add_argument(
            "--test", action="store_true", help="Run pipeline/automation tests"
        )
        parser.add_argument(
            "notebook", nargs="?", default=None, help="Jupyter notebook"
        )
        # add watch argument that watches the notebooks for changes and restarts if needed
        parser.add_argument(
            "--watch",
            action="store_true",
            help="Watch the notebook for changes and restarts if needed",
        )
        return parser

    def parse_arguments(self, args=None):
        args = super().parse_arguments(args=args)
        self.Test = args.test
        self.Notebook = args.notebook
        if self.Notebook is None:
            self.Notebook = os.environ.get("JUPYTER_NOTEBOOK", "pipelines/main.ipynb")
        self.Watch = args.watch

    async def main(self):
        print("{} pipeline(s) ready.".format(len(self.PumpService.Pipelines)))

        if self.Watch:
            from .watch import Watcher

            Watcher([self.Notebook])

    def _on_signal_usr1(self):
        """
        Description:

        :return:

        :hint: To clear reset from all pipelines, run
        $ kill -SIGUSR1 xxxx
        Equivalently, you can use `docker kill -s SIGUSR1 ....` to reset containerized BSPump.
        """
        # Reset errors from all pipelines
        for pipeline in self.PumpService.Pipelines.values():
            if not pipeline.is_error():
                continue  # Focus only on pipelines that has errors
            pipeline.set_error(None, None, None)
