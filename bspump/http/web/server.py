import logging
import traceback
import asyncio

from ...abc.source import Source
from ...abc.sink import Sink
from ...abc.connection import Connection

import aiohttp.web

#

L = logging.getLogger(__name__)


class WebServerConnection(Connection):
    """
    Source with events from a specific route.
    """

    ConfigDefaults = {
        "port": 8080,
        "max_body_size_bytes": 1024 * 1024 * 1000,
    }

    def __init__(self, app, id=None, config=None):
        super().__init__(app, id=id, config=config)

        self.aiohttp_app = aiohttp.web.Application(
            client_max_size=self.Config["max_body_size_bytes"]
        )
        self.start_server()

    def start_server(self):
        print("Starting webserver")
        try:
            self.App.Loop.create_task(
                aiohttp.web._run_app(
                    self.aiohttp_app,
                    port=self.Config["port"],
                )
            )
        except Exception as e:
            print("Exception: {}".format(e))
            import traceback

            traceback.print_exc()


class WebRouteSource(Source):
    """
    WebSource is a source that listens on a specified port and serves HTTP requests.
    """

    def __init__(
        self,
        app,
        pipeline,
        connection="DefaultWebServerConnection",
        method="GET",
        route="/",
        id=None,
        config=None,
    ):
        super().__init__(app, pipeline, id=id, config=config)
        pipeline.StopOnErrors = False

        self.Connection = pipeline.locate_connection(app, connection)
        self.aiohttp_app = self.Connection.aiohttp_app
        self.aiohttp_app.router.add_route(method, route, self.handle_request)

    async def main(self):
        pass

    async def handle_request(self, request):
        try:
            response_future = asyncio.Future()
            await self.process(
                {
                    "request": request,
                    "response_future": response_future,
                    "status": 200,
                }
            )
            return await response_future
        except Exception as e:
            L.exception("Exception in WebSource")
            return aiohttp.web.Response(status=500)


class ProtectedWebRouteSource(WebRouteSource):
    """
    Web route source that requires a secret in a qparam or in the BearerToken.
    """

    async def handle_request(self, request):
        try:
            secret = request.query.get("secret")
            if secret is None:
                auth = request.headers.get("Authorization")
                if auth is not None:
                    if auth.startswith("Bearer "):
                        secret = auth[7:]
            if secret is None:
                return aiohttp.web.Response(
                    text="Secret is missing. Pass via query parameter 'secret' or in the Authorization as 'Bearer <secret>'",
                    status=401,
                )

            if not self.Config.get("secret") == secret:
                return aiohttp.web.Response(text="Invalid secret", status=403)

            response_future = asyncio.Future()
            await self.process(
                {
                    "request": request,
                    "response_future": response_future,
                    "status": 200,
                }
            )
            return await response_future
        except Exception as e:
            L.exception("Exception in WebSource")
            return aiohttp.web.Response(status=500)


class Field:
    def __init__(self, name, **kwargs):
        self.name = name
        self.hidden = kwargs.get("hidden", False)
        self.readonly = kwargs.get("readonly", False)
        self.display = kwargs.get("display", self.name)
        self.default = kwargs.get("default", "")

    def clean(self, data):
        pass

    def html(self, default=""):
        if not default:
            default = self.default
        return f"""

      <div class="mt-10 grid grid-cols-1 gap-x-6 gap-y-8 sm:grid-cols-6" style='{'display: none' if self.hidden else ''}'>
        <div class="sm:col-span-4">
                <label for="{self.name}" class="block text-sm font-bold text-gray-700">{self.display}</label>
                {self.inner_html(default, self.readonly)}
        </div>
        </div>
        """


class TextField(Field):
    def inner_html(self, default="", readonly=False):
        if readonly:
            readonly = "readonly"
        else:
            readonly = ""
        return f"""
        <div class="mt-1">
            <input type="text" name="{self.name}" id="{self.name}" value="{default}" class="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block border-2 w-full sm:text-sm border-gray-300 rounded-md" {readonly}>
        </div>
        """


class ChoiceField(Field):
    def __init__(self, name, choices, **kwargs):
        super().__init__(name, **kwargs)
        self.choices = choices

    def inner_html(self, default="", readonly=False):
        if readonly:
            readonly = "readonly"
        else:
            readonly = ""
        return f"""
        <div class="mt-1">
            <select id="{self.name}" name="{self.name}" class="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block border-2 w-full sm:text-sm border-gray-300 rounded-md" {readonly}>
                {"".join(
                    f'<option value="{choice}" {"selected" if choice == default else ""}>{choice}</option>'
                    for choice in self.choices
                )}
            </select>
        </div>
        """


class CheckboxField(Field):
    def inner_html(self, default="", readonly=False):
        if readonly:
            readonly = "readonly"
        else:
            readonly = ""
        return f"""
            <input type="checkbox" name="{self.name}" id="{self.name}" {"checked" if default else ""} class="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block border-2 sm:text-sm border-gray-300 rounded-md" {readonly}>
        """

    def clean(self, data):
        data[self.name] = data.get(self.name, False) == "on"


class IntField(Field):
    def inner_html(self, default=0, readonly=False):
        if not default:
            default = 0
        if readonly:
            readonly = "readonly"
        else:
            readonly = ""
        return f"""
        <div class="mt-1">
            <input type="number" name="{self.name}" id="{self.name}" value="{default}" class="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block border-2 w-full sm:text-sm border-gray-300 rounded-md" {readonly}>
        </div>
        """

    def clean(self, data):
        data[self.name] = int(data.get(self.name, 0))


class FloatField(Field):
    def inner_html(self, default=0, readonly=False):
        if not default:
            default = 0.0
        if readonly:
            readonly = "readonly"
        else:
            readonly = ""
        return f"""
        <div class="mt-1">
            <input type="number" name="{self.name}" id="{self.name}" value="{default}" class="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block border-2 w-full sm:text-sm border-gray-300 rounded-md" {readonly}>
        </div>
        """

    def clean(self, data):
        data[self.name] = float(data.get(self.name, 0))


class WebFormSource(WebRouteSource):
    def __init__(
        self,
        app,
        pipeline,
        connection="DefaultWebServerConnection",
        route="/",
        fields=None,
        id=None,
        config=None,
    ):
        super().__init__(
            app,
            pipeline,
            connection=connection,
            route=route,
            method="GET",
            id=id,
            config=config,
        )
        self.fields = fields
        self.aiohttp_app.router.add_route("POST", route, self.handle_post)

    async def handle_request(self, request):
        return aiohttp.web.Response(
            text=self.render_form(request),
            content_type="text/html",
        )

    async def handle_post(self, request):
        data = dict(await request.post())
        for field in self.fields:
            try:
                field.clean(data)
            except ValueError as e:
                return aiohttp.web.Response(
                    text=self.render_form(request, errors={field.name: e}),
                    content_type="text/html",
                    status=400,
                )
        response_future = asyncio.Future()
        await self.process(
            {
                "request": request,
                "response_future": response_future,
                "status": 200,
                "form": data,
            }
        )
        return await response_future

    def render_form(self, request, errors={}):
        # read defaults from query params. If not present, use empty string.
        defaults = {
            field.name: request.query.get(field.name, "") for field in self.fields
        }
        top = f"""
        <html>
        <head>
        <script src="https://cdn.tailwindcss.com"></script>
        <script>

            function submitForm() {{
                document.getElementById("loading").style.display = "block";
                document.getElementById("main-form").submit();
            }}
        </script>
        </head>
        <BODY>
        <form id="main-form" method="post">
        <div id="loading" style="display:none">
            <div class="fixed top-0 left-0 h-screen w-screen bg-black bg-opacity-50 z-50 flex justify-center items-center">
                <div class="bg-white p-4 rounded-lg">
                    <div class="text-center">Processing...</div>
                </div>
            </div>
        </div>
        <div class="space-y-12">
        <div class="max-w-7xl mx-auto py-12 px-4 sm:px-6 lg:py-16 lg:px-8 bg-gray shadow sm:rounded-lg">
        """
        fields = ""
        for field in self.fields:
            fields += field.html(defaults[field.name])
            if field.name in errors:
                fields += f'<div class="text-red-500">{errors[field.name]}</div>'
        bottom = """
        <div class="mt-10 grid grid-cols-1 gap-x-6 gap-y-8 sm:grid-cols-6">
        <div class="sm:col-span-4">
        <button type="button" onclick=submitForm() class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded">Submit</button>
        </div>
        </div>
        </div>
        </div>
        </form>
        </body>
        </html>
        """
        return top + fields + bottom


class WebSink(Sink):
    """
    WebSink is a sink that sends HTTP requests.
    """

    def process(self, context, event):
        content_type = event.get("content_type", "text/html")
        event["response_future"].set_result(
            aiohttp.web.Response(
                status=event["status"],
                text=event["response"],
                content_type=content_type,
            )
        )


class JSONWebSink(Sink):
    """
    JSONWebSink is a sink that sends HTTP requests with JSON content.
    """

    def process(self, context, event):
        event["response_future"].set_result(
            aiohttp.web.json_response(event["response"], status=event["status"])
        )
