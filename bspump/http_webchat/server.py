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
import uuid

from jinja2 import Environment

import bspump
from bspump import Source, Connection, Sink
from bspump.http_webchat.webchat import WebChatPromptForm, WebChatTemplateEnv, WebChatResponse, WebChatWelcomeWindow, \
    FormInput

app = aiohttp.web.Application()
L = logging.getLogger(__name__)
'''
SESSIONS = {
    "session_id_1": {
        "username": "username_1",
        "chat_id": "chat_id_1",
    },
    ...
}

CHATS = {
    "chat_id_1": {
        "chat_history": [],
        "current_prompt": None,
        "registered_endpoints": []
    },
    ...
}
'''
SESSIONS = {}
CHATS = {}

def generate_session_id():
    return str(uuid.uuid4())

DEFAULT_CHAT_ID = "default-room"

@aiohttp.web.middleware
async def session_middleware(request, handler):
    session_id = request.cookies.get("session_id")

    if not session_id or session_id not in SESSIONS:
        session_id = generate_session_id()
        SESSIONS[session_id] = {"chat_id": DEFAULT_CHAT_ID, "username": "username_1"}

    request["session_id"] = session_id

    chat_id = SESSIONS[session_id]["chat_id"]
    if chat_id not in CHATS:
        CHATS[chat_id] = {
            "chat_history": [],
            "current_prompt": None,
            "registered_endpoints": []
        }

    request["chat_id"] = chat_id
    request["chat_data"] = CHATS[chat_id]

    response = await handler(request)

    if "session_id" not in request.cookies:
        response.set_cookie("session_id", session_id, httponly=True, max_age=3600*24*30)

    return response


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

async def set_prompt(form_inputs: list, submit_api_call: str = "/api/prompt_input_result", request=None) -> dict:
    pending_prompt_future = asyncio.get_event_loop().create_future()

    prompt_form = WebChatPromptForm(
        form_inputs, submit_api_call
    ).get_html(template_env=WebChatTemplateEnv().get_jinja_env())

    if request:
        request["session_data"]["current_prompt"] = prompt_form

    submitted_data = await pending_prompt_future
    request["session_data"]["chat_history"].append({
        "prompt": submitted_data
    })

    return submitted_data


async def parse_response_strings(flow_steps: list[str], template_env: Environment) -> AsyncGenerator[str, None]:
    context = {
        "WebChatResponse": WebChatResponse,
        "WebChatWelcomeWindow": WebChatWelcomeWindow,
        "WebChatPromptForm": WebChatPromptForm,
        "FormInput": FormInput,
        "set_prompt": set_prompt,
    }

    local_vars = {}

    for step in flow_steps:
        # print(step)
        try:
            if "\n" in step or "await" in step or "return" in step:
                if "await" in step or "return" in step:
                    exec_code = 'async def __temp_func():\n'
                    for line in step.splitlines():
                        exec_code += f'    {line}\n'
                    exec(exec_code, context, local_vars)
                    await local_vars["__temp_func"]()
                else:
                    exec(step, context, local_vars)

            else:
                try:
                    result = eval(step, context, local_vars)
                    if isinstance(result, (WebChatResponse, WebChatWelcomeWindow)):
                        yield result.get_html(template_env)
                except SyntaxError:
                    exec(step, context, local_vars)

        except Exception as e:
            print(f"Failed to process response string: {step}\nError: {e}")


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
            client_max_size=int(self.Config["max_body_size_bytes"]), middlewares=[session_middleware]
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
        # router.add_post("/api/prompt_input_result", prompt_input_result)
        # router.add_get("/ws", websocket_handler)
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


class WebchatSink(Sink):
    def process(self, context, item):
        response_future = item.get("response_future")
        if response_future and not response_future.done():
            response_future.set_result(aiohttp.web.Response(status=204))
