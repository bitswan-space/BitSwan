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

        try:
            self.Connection = pipeline.locate_connection(app, connection)
        except KeyError:
            if connection == "DefaultWebServerConnection":
                self.Connection = WebServerConnection(app, "DefaultWebServerConnection")
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


async def gate_response(request, expected_secret, response_fn):
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

    if not expected_secret == secret:
        return aiohttp.web.Response(text="Invalid secret", status=403)

    return await response_fn()


class ProtectedWebRouteSource(WebRouteSource):
    """
    Web route source that requires a secret in a qparam or in the BearerToken.
    """

    async def handle_request(self, request):
        try:

            async def response_fn():
                response_future = asyncio.Future()
                await self.process(
                    {
                        "request": request,
                        "response_future": response_future,
                        "status": 200,
                    }
                )
                return await response_future

            await gate_response(request, self.Config["secret"], response_fn)
        except Exception as e:
            L.exception("Exception in WebSource")
            return aiohttp.web.Response(status=500)


class FieldSet:
    def __init__(self, name, fields=None, fieldset_intro=""):
        self.fields = fields
        if fields is None:
            self.fields = []
        self.name = name
        self.default = {}
        self.fieldset_intro = fieldset_intro
        self.prefix = f"fieldset___{self.name}___"

    def set_subfield_names(self):
        for field in self.fields:
            field.field_name = f"{self.prefix}{field.name}"

    def html(self, defaults, *args, **kwargs):
        fields = ""
        self.set_subfield_names()
        for field in self.fields:
            fields += field.html(defaults.get(field.name, field.default))
        return f"""
        <div style="margin-left: 20px; border-left: 1px solid black; padding-left: 10px;margin-top: 30px;">
            <legend><b>{self.name}</b></legend>
            {self.fieldset_intro}
            {fields}
        </div>
        """

    def restructure_data(self, dfrom, dto):
        self.set_subfield_names()
        dto[self.name] = {}
        for field in self.fields:
            field.restructure_data(dfrom, dto[self.name])

    def clean(self, data):
        for field in self.fields:
            field.clean(data[self.name])


class Field:
    def __init__(self, name, **kwargs):
        self.name = name
        if "___" in name:
            raise ValueError("Field name cannot contain '___'")
        self.hidden = kwargs.get("hidden", False)
        self.readonly = kwargs.get("readonly", False)
        self.display = kwargs.get("display", self.name)
        self.default = kwargs.get("default", "")
        self.field_name = f"f___{self.name}"
        self.default_classes = kwargs.get(
            "default_css_classes",
            "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500",
        )
        if self.readonly:
            self.default_classes = kwargs.get(
                "default_css_classes",
                "bg-gray-500 border border-gray-300 text-white text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500",
            )

    @property
    def default_input_props(self):
        if self.readonly:
            readonly = "readonly"
        else:
            readonly = ""
        return f'name="{self.field_name}" id="{self.field_name}" {readonly}'

    def restructure_data(self, dfrom, dto):
        dto[self.name] = dfrom.get(self.field_name, self.default)

    def clean(self, data):
        pass

    def html(self, default=""):
        if not default:
            default = self.default
        return f"""

      <div class="mt-10 grid grid-cols-1 gap-x-6 gap-y-8 sm:grid-cols-6" style='{'display: none' if self.hidden else ''}'>
        <div class="sm:col-span-4">
                <label for="{self.field_name}" class="block text-sm font-bold text-gray-700">{self.display}</label>
                {self.inner_html(default, self.readonly)}
        </div>
        </div>
        """


class TextField(Field):
    def inner_html(self, default="", readonly=False):
        return f"""
        <div class="mt-1">
            <input type="text" class="{self.default_classes}" value="{default}" {self.default_input_props}>
        </div>
        """


class ChoiceField(Field):
    def __init__(self, name, choices, **kwargs):
        super().__init__(name, **kwargs)
        self.choices = choices

    def inner_html(self, default="", readonly=False):
        return f"""
        <div class="mt-1">
            <select class="{self.default_classes}" value="{default}" {self.default_input_props}>
                {"".join(
                    f'<option value="{choice}" {"selected" if choice == default else ""}>{choice}</option>'
                    for choice in self.choices
                )}
            </select>
        </div>
        """


class CheckboxField(Field):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default = self.default or False

    def inner_html(self, default="", readonly=False):
        return f"""
            <input type="checkbox" {"checked" if default == True or (default and default.lower() in ("true", "t")) else ""} class="{self.default_classes}" {self.default_input_props}>
        """

    def clean(self, data):
        if type(data.get(self.name)) == str:
            data[self.name] = data.get(self.name, False) == "on"


class IntField(Field):
    def inner_html(self, default=0, readonly=False):
        if not default:
            default = 0
        return f"""
        <div class="mt-1">
            <input type="number" value="{default}" class="{self.default_classes}" {self.default_input_props}>
        </div>
        """

    def clean(self, data):
        if type(data.get(self.name)) == str:
            data[self.name] = int(data.get(self.name, 0))


class FloatField(Field):
    def inner_html(self, default=0, readonly=False):
        if not default:
            default = 0.0
        return f"""
        <div class="mt-1">
            <input type="number" value="{default}" class="{self.default_classes}" {self.default_input_props}>
        </div>
        """

    def clean(self, data):
        if type(data.get(self.name)) == str:
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
        form_intro="",
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
        self.form_intro = form_intro
        self.aiohttp_app.router.add_route("POST", route, self.handle_post)

    async def handle_request(self, request):
        return aiohttp.web.Response(
            text=self.render_form(request),
            content_type="text/html",
        )

    async def handle_post(self, request):
        if request.content_type == "application/json":
            data = await request.json()
        else:
            dfrom = dict(await request.post())
            data = {}
            for field in self.fields:
                field.restructure_data(dfrom, data)
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
        # load defaults from request. Normal fields are listed by name. Subfields of fieldsets are listed as fieldset___subfield. We need to recursively go through this to support nested fieldsets. We should end up with a ntested dict of defaults
        defaults = {}
        for query_param, value in request.query.items():
            if "___" in query_param:
                parts = query_param.split("___")
                current_dict = defaults
                for fieldset in parts[:-1]:
                    if not current_dict.get(fieldset):
                        current_dict[fieldset] = {}
                    current_dict = current_dict[fieldset]
                current_dict[parts[-1]] = value
        for field in self.fields:
            if field.name in request.query:
                defaults[field.name] = request.query[field.name]
            elif field.name not in defaults:
                defaults[field.name] = field.default

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
        {self.form_intro}
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


class ProtectedWebFormSource(WebFormSource):
    async def handle_request(self, request):
        su = super()

        async def response_fn():
            return await su.handle_request(request)

        return await gate_response(request, self.Config["secret"], response_fn)

    async def handle_post(self, request):
        su = super()

        async def response_fn():
            return await su.handle_post(request)

        return await gate_response(request, self.Config["secret"], response_fn)


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
