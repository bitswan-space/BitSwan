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
WEBCHAT_FLOW_REGISTRY: dict[str, callable] = {}
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
                try:
                    import json
                    data = json.loads(msg.data)
                except Exception:
                    data = {}

                if data.get("type") == "ready":
                    ws._is_ready = True
                    CHATS[chat_id]["ready_event"].set()

                    '''
                    for item in CHATS[chat_id]["chat_history"]:
                        if "response" in item:
                            response_html = WebChatResponse(input_html=item["response"]).get_html(
                                template_env=WebChatTemplateEnv().get_jinja_env()
                            )
                            await ws.send_str(response_html)

                    current_prompt = CHATS[chat_id].get("current_prompt")
                    if current_prompt:
                        await ws.send_str(current_prompt)
                        
                    '''
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
    await chat_data["ready_event"].wait()

    future = asyncio.get_event_loop().create_future()
    prompt_html = WebChatPromptForm(form_inputs).get_html(
        template_env=WebChatTemplateEnv().get_jinja_env()
    )

    chat_data["current_prompt"] = prompt_html
    chat_data["_pending_prompt_future"] = future

    websockets = WEBSOCKETS.get(chat_id, set())
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
    await chat_data["ready_event"].wait()

    websockets = WEBSOCKETS.get(chat_id, set())
    chat_data["chat_history"].append({"response": response_text})

    for ws in list(websockets):
        try:
            await ws.send_str(response.get_html(template_env=WebChatTemplateEnv().get_jinja_env()))
        except Exception:
            websockets.discard(ws)

async def parse_response_strings(flow_steps: list[str], template_env: Environment) -> AsyncGenerator[str, None]:
    context = {
        "WebChatResponse": WebChatResponse,
        "WebChatWelcomeWindow": WebChatWelcomeWindow,
        "WebChatPromptForm": WebChatPromptForm,
        "FormInput": FormInput,
        "set_prompt": set_prompt,
        "tell_user": tell_user,
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


async def redirect(flow_name: str, event):
    flow_func = WEBCHAT_FLOW_REGISTRY.get(flow_name)
    if not flow_func:
        raise ValueError(f"Flow '{flow_name}' not registered")
    await flow_func(event)

def create_webchat_flow(name: str):
    def decorator(func):
        WEBCHAT_FLOW_REGISTRY[name] = func
        return func
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
        router.add_get("/ws", websocket_handler)
        router.add_get("/api/proxy", general_proxy)
        self.aiohttp_app.router.add_static("/static", os.path.join(self.base_dir, "static"))
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

        chat_data = CHATS[decode_chat_token(bearer_token)]
        # Generate chat history HTML as one big chunk
        chat_history_html = ""
        for item in chat_data["chat_history"]:
            if "response" in item:
                html = WebChatResponse(input_html=item["response"]).get_html(
                    template_env=template_env
                )
            else:
                continue
            chat_history_html += html

        current_prompt_html = chat_data.get("current_prompt", "")


        context = {
            "welcome_html": welcome_html,
            "bearer_token": bearer_token,
            "current_prompt_html": current_prompt_html,
            "chat_history_html": chat_history_html,
            "chats": [
                {
                    "chat_id": chat_id,
                    "token": bearer_token
                }
                for chat_id in CHATS.keys()
            ]
        }

        if not chat_data.get("started"):
            await self.pipeline.process({"bearer_token": bearer_token})
            chat_data["started"] = True

        return aiohttp_jinja2.render_template("index.html", request, context)

    async def handle_request(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        if request.method != "GET":
            return aiohttp.web.Response(status=405)

        token = request.query.get("chat_id")
        chat_id = None

        if not token:
            # Create new chat session and redirect with token
            chat_id = str(uuid.uuid4())
            token = generate_bearer_token(chat_id)
            print(f"Generated NEW token for new chat_id={chat_id}: {token}")
            location = f"/?chat_id={token}"
            raise aiohttp.web.HTTPFound(location)

        # If token is present, validate it
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            chat_id = payload.get("chat_id")
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as e:
            print(f"Invalid or expired token: {e}")
            # invalid token, create new chat and redirect
            chat_id = str(uuid.uuid4())
            token = generate_bearer_token(chat_id)
            print(f"Generated NEW token for new chat_id={chat_id}: {token}")
            location = f"/?chat_id={token}"
            raise aiohttp.web.HTTPFound(location)

        if chat_id not in CHATS:
            CHATS[chat_id] = {
                "chat_history": [],
                "current_prompt": None,
                "ready_event": asyncio.Event(),
                "started": False
            }
            print(f"Initialized chat store for chat_id={chat_id}")
        else:
            print(CHATS[chat_id]["chat_history"], CHATS[chat_id]["current_prompt"])
        return await self.serve_index(request, bearer_token=token)


class WebchatSink(Sink):
    def process(self, context, item):
        response_future = item.get("response_future")
        if response_future and not response_future.done():
            response_future.set_result(aiohttp.web.Response(status=204))
