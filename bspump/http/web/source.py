import logging

from ...abc.source import Source

#

L = logging.getLogger(__name__)


def add_context_from_request(request, context):
    # Prepare context variables
    context["webservicesource.remote"] = request.remote
    context["webservicesource.path"] = request.path
    context["webservicesource.query"] = request.query
    context["webservicesource.headers"] = request.headers
    context["webservicesource.secure"] = request.secure
    context["webservicesource.method"] = request.method
    context["webservicesource.url"] = request.url
    context["webservicesource.scheme"] = request.scheme
    context["webservicesource.forwarded"] = request.forwarded
    context["webservicesource.host"] = request.host
    context["webservicesource.cookies"] = request.cookies
    context["webservicesource.content_type"] = request.content_type
    context["webservicesource.charset"] = request.charset
    return context


class WebServiceSource(Source):
    """
    This source is to be integrated into aiohttp.web as a 'View'.

    Example:
            async def view(self, request):
                    await self.WebServiceSource.put(None, data, request)
                    return aiohttp.web.Response(text='OK')

    """

    async def put(self, context, data, request):
        if context is None:
            context = {}

        add_context_from_request(request, context)
        await self.Pipeline.ready()
        await self.process(data, context)

    async def main(self):
        pass


class WebHookSource(Source):
    """
    Creates a webhook endpoint as configured in the configuration file.

    Configuration example:
    config = {
        "path": "/webhook",
        "port": 8080,
        "secret_qparam": "secret",
    }

    This will create a webhook endpoint at http://localhost:8080/webhook?secret=SECRET
    """

    ConfigDefaults = {
        "path": "webhook/",
        "port": "8080",
        "max_body_size_bytes": 1024 * 1000 * 1000,
    }

    def __init__(self, app, pipeline, id=None, config=None):
        """
        Initializes parameters.

        **Parameters**

        app : Application
                Name of the `Application <https://asab.readthedocs.io/en/latest/asab/application.html#>`_.

        pipeline : Pipeline
                Name of the Pipeline.

        id : , default = None

        config : , default = None

        """
        super().__init__(app, pipeline, id=id, config=config)

        self.App = app

    async def main(self):
        import aiohttp.web

        aiohttp_app = aiohttp.web.Application(
            client_max_size=self.Config["max_body_size_bytes"]
        )
        print("Adding routes to webserver")
        aiohttp_app.add_routes(
            [aiohttp.web.post(self.Config["path"], self.handle_post)]
        )
        print("Starting webserver")
        try:
            self.App.Loop.create_task(
                aiohttp.web._run_app(
                    aiohttp_app,
                    port=self.Config["port"],
                )
            )
        except Exception as e:
            print("Exception: {}".format(e))
            # print full traceback
            import traceback

            traceback.print_exc()

    async def handle_post(self, request):
        import aiohttp.web

        try:
            if self.Config.get("secret_qparam") is not None:
                secret = request.query.get("secret")
                if secret is None:
                    return aiohttp.web.Response(status=403, text="Missing secret")
                if secret != self.Config.get("secret_qparam"):
                    return aiohttp.web.Response(status=403, text="Invalid secret")
            body = await request.text()
            context = {}
            add_context_from_request(request, context)

            await self.process(body, context)
            return aiohttp.web.Response(text="Processed successfully")

        except Exception as e:
            L.exception("Error when processing POST request")
            self.Pipeline.set_error(None, None, e)
            return aiohttp.web.Response(text="Error processing request", status=500)
