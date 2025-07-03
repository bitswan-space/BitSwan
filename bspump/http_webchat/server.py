import asyncio
import re
from typing import Callable, AsyncGenerator
import logging

import aiohttp.web
import aiohttp_jinja2
import jinja2
import os
import uuid
import jwt
import datetime
from jinja2 import Environment
from dotenv import load_dotenv

from bspump import Source, Connection, Sink
from bspump.http_webchat.webchat import WebChatPromptForm, WebChatTemplateEnv, WebChatResponse, WebChatWelcomeWindow, \
    FormInput

'''
CHATS = {
    "chat_id_1": {
        "chat_history": [],
        "current_prompt": None,
    },
    ...
}
'''
load_dotenv()
L = logging.getLogger(__name__)
CHATS = {}
WEBSOCKETS = {}
_registered_endpoints = {}

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET is not set in the environment!")

def decode_chat_token(token: str) -> str:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload["chat_id"]
    except jwt.ExpiredSignatureError:
        # token expired
        raise
    except jwt.InvalidTokenError:
        # invalid token
        raise

async def websocket_handler(request):
    ws = aiohttp.web.WebSocketResponse()
    await ws.prepare(request)

    bearer_token = request.rel_url.query.get("chat_id")
    if not bearer_token:
        await ws.close(message=b"No chat_id token")
        return ws

    try:
        decoded = jwt.decode(bearer_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        chat_id = decoded["chat_id"]
    except Exception:
        await ws.close(message=b"Invalid or expired token")
        return ws

    WEBSOCKETS.setdefault(chat_id, set()).add(ws)
    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                print(f"Received message from client: {msg.data}")
                try:
                    import json
                    data = json.loads(msg.data)
                except Exception:
                    data = {}

                if data.get("type") == "ready":
                    print(f"WebSocket client ready for chat_id={chat_id}")
                    ws._is_ready = True
                    CHATS[chat_id]["ready_event"].set()

                elif data.get("type") == "prompt_submission":
                    submitted_data = data.get("data")
                    pending = CHATS[chat_id].get("_pending_prompt_future")
                    if pending and not pending.done():
                        pending.set_result(submitted_data)

            elif msg.type == aiohttp.WSMsgType.ERROR:
                print(f"WS connection closed with exception {ws.exception()}")
                break

    except Exception as e:
        print(f"WebSocket exception: {e}")
    finally:
        WEBSOCKETS[chat_id].discard(ws)
        print(f"WebSocket disconnected: chat_id={chat_id}, remaining connections: {len(WEBSOCKETS.get(chat_id, []))}")

    return ws

def generate_session_id():
    return str(uuid.uuid4())

async def general_proxy(request):
    target_url = request.query.get("url")
    if not target_url or not re.match(r"^https?://", target_url):
        return aiohttp.web.Response(status=400, text="Invalid or missing URL")
    if "127.0.0.1" in target_url or "localhost" in target_url:
        return aiohttp.web.Response(status=403, text="Access to internal resources is forbidden")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(target_url) as resp:
                body = await resp.text()
                return aiohttp.web.Response(text=body, content_type="text/html")
    except Exception as e:
        return aiohttp.web.Response(status=500, text=f"Proxy error: {str(e)}")

async def set_prompt(form_inputs: list, bearer_token: str) -> dict:
    payload = jwt.decode(bearer_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    chat_id = payload["chat_id"]
    chat_data = CHATS[chat_id]

    # Wait until the WebSocket is ready (someone sent the "ready" message)
    print(f"Waiting for WebSocket client to be ready for chat_id={chat_id}...")
    await chat_data["ready_event"].wait()
    print(f"WebSocket ready for chat_id={chat_id}, sending prompt.")

    future = asyncio.get_event_loop().create_future()
    prompt_html = WebChatPromptForm(form_inputs).get_html(
        template_env=WebChatTemplateEnv().get_jinja_env()
    )

    chat_data["current_prompt"] = prompt_html
    chat_data["_pending_prompt_future"] = future

    websockets = WEBSOCKETS.get(chat_id, set())
    print("websockets", websockets)
    for ws in websockets.copy():
        try:
            print(f"Sending prompt to WebSocket: {ws}")
            await ws.send_str(prompt_html)
        except Exception as e:
            WEBSOCKETS[chat_id].discard(ws)
            print(f"WebSocket error for chat_token={chat_id}: {e}")

    submitted_data = await future
    awaiting_html = WebChatPromptForm([], awaiting_text='Awaiting prompt from server...'
        ).get_html(
            template_env=WebChatTemplateEnv().get_jinja_env()
        )
    chat_data["current_prompt"] = awaiting_html

    for ws in websockets.copy():
        try:
            print(f"Sending awaiting prompt to WebSocket: {ws}")
            await ws.send_str(awaiting_html)
        except Exception as e:
            WEBSOCKETS[chat_id].discard(ws)
            print(f"WebSocket error for chat_token={chat_id}: {e}")

    chat_data["chat_history"].append({"prompt": submitted_data})
    return submitted_data


async def tell_user(response_text, bearer_token):
    response = WebChatResponse(input_html=response_text)
    payload = jwt.decode(bearer_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    chat_id = payload["chat_id"]
    chat_data = CHATS[chat_id]

    # Wait for WebSocket client to be ready
    print(f"Waiting for WebSocket client to be ready for chat_id={chat_id}...")
    await chat_data["ready_event"].wait()
    print(f"WebSocket ready for chat_id={chat_id}, sending response.")

    websockets = WEBSOCKETS.get(chat_id, set())
    chat_data["chat_history"].append({"response": response_text})

    for ws in list(websockets):
        try:
            await ws.send_str(response.get_html(template_env=WebChatTemplateEnv().get_jinja_env()))
        except Exception:
            websockets.discard(ws)

async def parse_response_strings(flow_steps: list[str], template_env: Environment, request) -> AsyncGenerator[str, None]:
    context = {
        "WebChatResponse": WebChatResponse,
        "WebChatWelcomeWindow": WebChatWelcomeWindow,
        "WebChatPromptForm": WebChatPromptForm,
        "FormInput": FormInput,
        "set_prompt": lambda *args, **kwargs: set_prompt(*args, request=request, **kwargs),
    }
    local_vars = {}

    for step in flow_steps:
        try:
            if "await" in step or "return" in step:
                exec_code = "async def __temp_func():\n" + "\n".join(f"    {line}" for line in step.splitlines())
                exec(exec_code, context, local_vars)
                await local_vars["__temp_func"]()
            else:
                result = eval(step, context, local_vars)
                if isinstance(result, (WebChatResponse, WebChatWelcomeWindow)):
                    yield result.get_html(template_env)
        except Exception as e:
            print(f"Error executing step:\n{step}\n{e}")


def create_webchat_flow(route: str):
    def decorator(func: Callable):
        async def wrapped(request):
            try:
                flow = await func(request)
                template_env = WebChatTemplateEnv().get_jinja_env()
                resp = aiohttp.web.StreamResponse(status=200, headers={"Content-Type": "text/html"})
                await resp.prepare(request)
                async for fragment in parse_response_strings(flow, template_env, request):
                    await resp.write(fragment.encode("utf-8"))
                await resp.write_eof()
                return resp
            except Exception as e:
                return aiohttp.web.Response(status=500, text=f"Error: {e}")
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

        # http://0.0.0.0:8080/?chat_id=1
        self.aiohttp_app = aiohttp.web.Application(
            client_max_size=int(self.Config["max_body_size_bytes"]))

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

def generate_bearer_token(chat_id: str) -> str:
    payload = {
        "chat_id": chat_id,
        "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

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

    async def serve_index(self, request: aiohttp.web.Request, bearer_token) -> aiohttp.web.Response:
        template_env = WebChatTemplateEnv().get_jinja_env()
        welcome_html = self.welcome_window.get_html(template_env)
        context = {
            "welcome_html": welcome_html,
            "bearer_token": bearer_token
        }

        await self.pipeline.process({"bearer_token": bearer_token})

        return aiohttp_jinja2.render_template("index.html", request, context)

    # nahodne chat_id, generovat token a poslem do serve_index
    # ten isty chat_id poslem do self.pipeline.process(chat_id)
    # a ked dam set_prompt tak vyhladam websocket podla chat_id
    # zavriem websocket ak token nie je platny, bearer token
    # chat_id ziskam v notebooku z eventu

    async def handle_request(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        if request.method != "GET":
            return aiohttp.web.Response(status=405)

        token = request.query.get("chat_id")
        chat_id = None

        if token:
            try:
                payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
                chat_id = payload.get("chat_id")
            except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as e:
                print(f"Invalid or expired token: {e}")
                token = None
                chat_id = None

        if not chat_id:
            chat_id = str(uuid.uuid4())
            token = generate_bearer_token(chat_id)
            print(f"Generated NEW token for new chat_id={chat_id}: {token}")
            location = f"/?chat_id={token}"
            raise aiohttp.web.HTTPFound(location)

        if chat_id not in CHATS:
            CHATS[chat_id] = {
                "chat_history": [],
                "current_prompt": None,
                "ready_event": asyncio.Event()
            }
            print(f"Initialized chat store for chat_id={chat_id}")

        return await self.serve_index(request, bearer_token=token)


class WebchatSink(Sink):
    def process(self, context, item):
        response_future = item.get("response_future")
        if response_future and not response_future.done():
            response_future.set_result(aiohttp.web.Response(status=204))
