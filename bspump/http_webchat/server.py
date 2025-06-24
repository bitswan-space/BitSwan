import asyncio
import importlib.util
import json
import re
import time
from typing import Callable, List, Any, AsyncGenerator, Coroutine
import logging

import aiohttp.web
import aiohttp_jinja2
import jinja2
import os

from jinja2 import Environment

import bspump
from bspump import Source, Connection, Sink

app = aiohttp.web.Application()
L = logging.getLogger(__name__)


class WebChatTemplateEnv:
    def __init__(self, extra_template_dir: str = None):
        """
        Creates template environment on user side that will be then used for creating other components
        :param extra_template_dir: path to template directory, could be none, because user can specify the templates as strings
        """
        self.extra_template_dir = extra_template_dir
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.template_env = self.create_template_env()

    def create_template_env(self) -> Environment:
        main_template_dir = os.path.join(self.base_dir, "templates")
        loader_paths = []

        if not os.path.isdir(main_template_dir):
            raise ValueError(f"Template directory '{main_template_dir}' does not exist")
        loader_paths.append(main_template_dir)

        if self.extra_template_dir:
            loader_paths.append(self.extra_template_dir)

        aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(loader_paths))

        template_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(loader_paths),
            autoescape=jinja2.select_autoescape(["html", "xml"]),
        )

        return template_env

    def get_jinja_env(self) -> Environment:
        """
        :return: Environment variable
        """
        return self.template_env


class FormInput:
    def __init__(
        self,
        label: str,
        name: str,
        input_type: str,
        step: float | int = None,
        required=False,
    ):
        """
        Class for defining one input field
        :param label: Text next to input window
        :param name: Identifier of input
        :param input_type: html input type
        :param step: can be floating point number or integer
        :param required: html input required parameter
        """
        self.label = label
        self.name = name
        self.input_type = input_type
        self.step = step
        self.required = required

# this returns the final html for the prompt, and then I want to render this instead of prompt
class WebChatPromptForm:
    def __init__(self, form_inputs: List[FormInput], submit_api_call: str):
        """
        Class for defining of form
        :param form_inputs: list of individual input fields
        :param submit_api_call: where the data should be submitted
        """
        self.form_inputs = form_inputs
        self.submit_api_call = submit_api_call

    def get_context(self) -> dict:
        context = {
            "response_box_api": self.submit_api_call,
            "form_inputs": self.form_inputs,
            "form_id": f"prompt-form-{int(time.time() * 1000)}",
        }
        return context

    def get_html(self, template_env: Environment) -> str:
        template = template_env.get_template("components/prompt-form.html")
        return template.render(self.get_context())


class WebChatWelcomeWindow:
    def __init__(self, welcome_text: str):
        """
        Class for defining the first window that is rendered and is visible all the time
        :param welcome_text: text or html string that should be rendered
        :param prompt_form: html of the prompt that is rendered with the window
        """
        self.welcome_text = welcome_text or ""

    def get_context(self, template_env: Environment) -> dict:
        context = {
            "welcome_text": self.welcome_text,
        }
        return context

    def get_html(self, template_env: Environment) -> str:
        template = template_env.get_template("components/welcome-message-box.html")
        return template.render(self.get_context(template_env))


class WebChatResponse:
    def __init__(
        self,
        input_html: str,
        prompt_form: WebChatPromptForm = None,
        api_endpoint: str = None,
    ):
        """
        Class for creating one response
        :param input_html: could be just string or html string
        :param prompt_form: html of the prompt that is rendered with the window
        :param api_endpoint: endpoint string if the response should make a api request
        """
        self.input_html = input_html or ""
        self.prompt_form = prompt_form
        self.api_endpoint = api_endpoint

    def get_context(self, template_env: Environment) -> dict:
        return {
            "response_text": self.input_html,
            "prompt_html": self.prompt_form.get_html(template_env)
            if self.prompt_form
            else "",
            "api_endpoint": self.api_endpoint if self.api_endpoint else "",
            "has_prompt": bool(self.prompt_form),
        }

    def get_html(self, template_env: Environment) -> str:
        if self.api_endpoint:
            template = template_env.get_template(
                "components/web-chat-response-with-request.html"
            )
        else:
            template = template_env.get_template("components/web-chat-response.html")
        return template.render(self.get_context(template_env))


class WebChatResponseSequence:
    def __init__(self, responses: List[WebChatResponse]):
        """
        Class that defines and renders sequence of responses
        :param responses: list of instances of class WebChatResponse
        """
        self.responses = responses

    def get_html(self, template_env: Environment) -> str:
        rendered_responses = [
            response.get_html(template_env) for response in self.responses
        ]
        js_safe_responses = json.dumps(rendered_responses)
        context = {
            "responses": js_safe_responses,
        }
        template = template_env.get_template(
            "components/web-chat-sequence-response.html"
        )
        return template.render(context)


async def general_proxy(request):
    target_url = request.query.get("url")
    if not target_url or not re.match(r"^https?://", target_url):
        return aiohttp.web.Response(status=400, text="Invalid or missing URL")
    if "127.0.0.1" in target_url or "localhost" in target_url:
        return aiohttp.web.Response(
            status=403, text="Access to internal resources is forbidden"
        )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(target_url) as resp:
                body = await resp.text()
                return aiohttp.web.Response(text=body, content_type="text/html")
    except Exception as e:
        return aiohttp.web.Response(status=500, text=f"Proxy error: {str(e)}")


_registered_endpoints = {}

def find_module_path(module_name):
    spec = importlib.util.find_spec(module_name)
    if spec and spec.origin:
        return spec.origin
    else:
        return f"Module '{module_name}' not found or built-in."

async def parse_response_strings(response_strings: list[str], template_env: Environment) -> AsyncGenerator[str, None]:
    context = {
        "WebChatResponse": WebChatResponse,
        "WebChatWelcomeWindow": WebChatWelcomeWindow,
        "WebChatPromptForm": WebChatPromptForm,
        "FormInput": FormInput,
        "set_prompt": set_prompt,
    }

    local_vars = {}

    for response_str in response_strings:
        try:
            if "\n" in response_str or "await" in response_str or "return" in response_str:
                if "await" in response_str or "return" in response_str:
                    exec_code = 'async def __temp_func():\n'
                    for line in response_str.splitlines():
                        exec_code += f'    {line}\n'

                    exec(exec_code, context, local_vars)
                    result = await local_vars['__temp_func']()

                    if isinstance(result, (WebChatResponse, WebChatWelcomeWindow)):
                        yield result.get_html(template_env)
                else:
                    exec(response_str, context, local_vars)

            else:
                try:
                    result = eval(response_str, context, local_vars)
                    if isinstance(result, (WebChatResponse, WebChatWelcomeWindow)):
                        yield result.get_html(template_env)
                except SyntaxError:
                    exec(response_str, context, local_vars)

        except Exception as e:
            print(f"Failed to process response string: {response_str}\nError: {e}")

def create_webchat_flow(route: str):

    def decorator(func: Callable):
        async def wrapped(request):
            try:
                response_code_list = await func(request)
                template_env = WebChatTemplateEnv().get_jinja_env()

                resp = aiohttp.web.StreamResponse(status=200, reason='OK', headers={'Content-Type': 'text/html'})
                await resp.prepare(request)

                async for fragment in parse_response_strings(response_code_list, template_env):
                    await resp.write(fragment.encode('utf-8'))

                await resp.write_eof()
                return resp

            except Exception as e:
                return aiohttp.web.Response(status=500, text=f"Error: {str(e)}")

        _registered_endpoints[route] = wrapped
        return wrapped

    return decorator


class WebChatServerConnection(Connection):

    ConfigDefaults = {
        "port": 8080,
        "max_body_size_bytes": 1024 * 1024 * 1000,
    }

    def __init__(self, app, id=None, config=None):
        super().__init__(app, id=id, config=config)

        self.aiohttp_app = aiohttp.web.Application(
            client_max_size=int(self.Config["max_body_size_bytes"])
        )
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        aiohttp_jinja2.setup(
            self.aiohttp_app,
            loader=jinja2.FileSystemLoader(os.path.join(self.base_dir, "templates")),
        )
        router = self.aiohttp_app.router
        if _registered_endpoints:
            for route, handler in _registered_endpoints.items():
                router.add_route("*", route, handler)
        router.add_post("/api/prompt_input_result", handle_prompt_input_result)
        router.add_get("/ws", websocket_handler)
        router.add_get("/api/proxy", general_proxy)
        self.aiohttp_app.router.add_static("/static", os.path.join(self.base_dir, "static"))
        # static_dir = str(files("bspump").joinpath("styles")) add once the tailwind from cdn is removed
        # self.aiohttp_app.router.add_static("/styles/", static_dir, show_index=True)
        self.start_server()

    def start_server(self):
        print("Starting webchat server")
        try:
            self.App.Loop.create_task(
                aiohttp.web._run_app(
                    self.aiohttp_app,
                    port=int(self.Config["port"]),
                )
            )
        except Exception as e:
            print("Exception: {}".format(e))
            import traceback

            traceback.print_exc()


class WebChatRouteSource(Source):
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
                try:
                    default_port = int(
                        os.environ.get("DEFAULT_WEB_SERVER_CONNECTION_PORT") or "8080"
                    )
                except ValueError:
                    default_port = 8080
                    L.warning(
                        "DEFAULT_WEB_SERVER_CONNECTION_PORT is not a valid integer. Using default value {}.".format(
                            default_port
                        )
                    )

                self.Connection = WebChatServerConnection(
                    app,
                    "DefaultWebServerConnection",
                    {"port": default_port},
                )
                app.PumpService.add_connection(self.Connection)
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
        except Exception:
            L.exception("Exception in WebSource")
            return aiohttp.web.Response(status=500)

class WebChatSource(WebChatRouteSource):

    def __init__(self, app, pipeline, welcome_text, connection="DefaultWebServerConnection",
        route="/", id=None, config=None):
        super().__init__(
            app,
            pipeline,
            connection=connection,
            route=route,
            method="GET",
            id=id,
            config=config,
        )

        self.pipeline = pipeline
        self.welcome_window = welcome_text

    async def trigger_start_event(self):
        fake_event = {}
        await self.pipeline.process(fake_event)

    async def serve_index(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        template_env = WebChatTemplateEnv().get_jinja_env()
        welcome_html = self.welcome_window.get_html(template_env)
        context = {"welcome_html": welcome_html}
        await self.trigger_start_event()
        return aiohttp_jinja2.render_template("index.html", request, context)

    async def handle_request(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        if request.method == "GET":
            return await self.serve_index(request)
        return aiohttp.web.Response(status=405)


current_prompt_html = "<p>Initial prompt</p>"
ws_connections = set()
pending_prompt_future: asyncio.Future | None = None

async def set_prompt(
    form_inputs: list,
    submit_api_call: str = "/api/prompt_input_result"
) -> dict:
    global current_prompt_html, pending_prompt_future

    pending_prompt_future = asyncio.get_event_loop().create_future()

    prompt_form = WebChatPromptForm(
        form_inputs, submit_api_call
    ).get_html(template_env=WebChatTemplateEnv().get_jinja_env())

    current_prompt_html = prompt_form

    for ws in ws_connections.copy():
        try:
            await ws.send_str(prompt_form)
        except Exception:
            ws_connections.discard(ws)

    submitted_data = await pending_prompt_future
    pending_prompt_future = None
    return submitted_data

async def handle_prompt_input_result(request: aiohttp.web.Request):
    data = await request.post()
    print("Received form input data:", dict(data))

    global pending_prompt_future
    if pending_prompt_future is not None and not pending_prompt_future.done():
        pending_prompt_future.set_result(dict(data))

    return aiohttp.web.Response(text="<p class='text-sm'>Data received. Thank you.</p>")

# websocket handler that pushes the prompt html to frontend
async def websocket_handler(request):
    ws = aiohttp.web.WebSocketResponse()
    await ws.prepare(request)

    ws_connections.add(ws)

    try:
        await ws.send_str(current_prompt_html)

        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                pass
            elif msg.type == aiohttp.WSMsgType.ERROR:
                print(f"WebSocket connection closed with exception: {ws.exception()}")

    finally:
        ws_connections.remove(ws)
        await ws.close()

    return ws


class WebchatSink(Sink):
    def process(self, context, item):
        response_future = item.get("response_future")
        if response_future and not response_future.done():
            response_future.set_result(aiohttp.web.Response(status=204))
