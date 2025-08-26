"""
WebChat Server Module

This module provides a complete WebChat server implementation for BSPump pipelines.
It includes WebSocket handling, JWT authentication, chat session management,
and HTTP routing for interactive web-based chat interfaces.

Key Components:
- WebChatFlow: Main chat flow controller
- WebChatServerConnection: HTTP server connection
- WebChatRouteSource: HTTP route source for chat endpoints
- WebChatSource: Main chat source component
- WebchatSink: Response sink component
"""

import asyncio
import inspect
import re
import logging

import aiohttp.web
import aiohttp_jinja2
import jinja2
import os
import uuid
import jwt
import datetime
from dotenv import load_dotenv

from bspump import Source, Connection, Sink
from bspump.http_webchat.webchat import (
    WebChatPromptForm,
    WebChatTemplateEnv,
    WebChatResponse,
    PromptFormBaseField,
    WebChatWelcomeWindow,
)

# Load environment variables from .env file
load_dotenv()

# Configure basic logging for the module
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

# Module logger
L = logging.getLogger(__name__)

# Global storage for chat sessions and WebSocket connections
CHATS = {}  # Stores chat data by chat_id
WEBSOCKETS = {}  # Stores WebSocket connections by chat_id
WEBCHAT_FLOW_REGISTRY: dict[str, callable] = {}  # Registry of available chat flows
_registered_endpoints = {}  # Custom endpoint handlers

# JWT configuration - can be set via environment variables or configuration
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"

# This will be overridden by configuration if provided
if not JWT_SECRET:
    L.warning(
        "JWT_SECRET not set in environment. Will use configuration-based secret if provided."
    )


def get_jwt_secret(config=None):
    """
    Get JWT secret from config, environment variable, or global config system.

    Priority order:
    1. Config dict parameter
    2. Environment variable
    3. Global BSPump configuration

    Args:
        config: Optional configuration dictionary

    Returns:
        str: JWT secret string

    Raises:
        RuntimeError: If no JWT secret can be found
    """
    # Config dict
    if config and "JWT_SECRET" in config:
        L.info("Loaded JWT secret from config")
        return str(config["JWT_SECRET"])

    # Module/global
    if JWT_SECRET:
        L.info("Loaded JWT secret from environment")
        return str(JWT_SECRET)

    # OS environment
    env_secret = os.getenv("JWT_SECRET")
    if env_secret:
        L.info("Loaded JWT secret from environment")
        return str(env_secret)

    # Global config
    try:
        from bspump.asab import Config

        for section in Config.sections():
            if section.startswith("pipeline:") and "JWT_SECRET" in Config[section]:
                secret = Config[section]["JWT_SECRET"]
                L.info(f"Loaded JWT secret from global config section: {section}")
                return str(secret)
    except Exception as e:
        L.debug(f"Could not access global config: {e}")

    raise RuntimeError(
        "JWT_SECRET not configured (no config, env, or global config found)"
    )


def recursive_merge(dict1, dict2):
    """
    Recursively merge two dictionaries, with values from dict2 taking precedence.

    Args:
        dict1: Base dictionary
        dict2: Dictionary with values to merge (takes precedence)

    Returns:
        dict: Merged dictionary
    """
    for key, value in dict2.items():
        if key in dict1 and isinstance(dict1[key], dict) and isinstance(value, dict):
            dict1[key] = recursive_merge(dict1[key], value)
        else:
            dict1[key] = value
    return dict1


def generate_session_id():
    """Generate a unique session ID using UUID4."""
    return str(uuid.uuid4())


def generate_bearer_token(chat_id: str, config: dict = None) -> str:
    """
    Generate a JWT bearer token for a chat session.

    Args:
        chat_id: Unique identifier for the chat session
        config: Optional configuration dictionary

    Returns:
        str: JWT token string
    """
    secret = get_jwt_secret(config)
    expiry_hours = 1

    payload = {
        "chat_id": chat_id,
        "exp": datetime.datetime.now(datetime.UTC)
        + datetime.timedelta(hours=expiry_hours),
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def decode_chat_token(token: str, config: dict = None) -> str:
    """
    Decode JWT token and extract chat_id with improved error handling.

    Args:
        token: JWT token string to decode
        config: Optional configuration dictionary

    Returns:
        str: Extracted chat_id from token

    Raises:
        jwt.ExpiredSignatureError: If token has expired
        jwt.InvalidTokenError: If token is invalid
        ValueError: If token payload is missing required fields
    """
    secret = get_jwt_secret(config)

    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
        return payload["chat_id"]
    except jwt.ExpiredSignatureError as e:
        L.warning(f"JWT token expired: {e}")
        raise
    except jwt.InvalidTokenError as e:
        L.warning(f"Invalid JWT token: {e}")
        raise
    except KeyError as e:
        L.error(f"JWT payload missing required field 'chat_id': {e}")
        raise ValueError("JWT payload missing required field 'chat_id'")


def validate_jwt_token(token: str, config: dict = None) -> tuple[bool, str, dict]:
    """
    Validate JWT token and return validation status, error message, and payload.
    This provides comprehensive validation similar to JWTWebFormSource.test_secret.

    Args:
        token: JWT token string to validate
        config: Optional configuration dictionary

    Returns:
        tuple: (is_valid, error_message, payload)
        - is_valid: boolean indicating if token is valid
        - error_message: error description if invalid, empty string if valid
        - payload: decoded JWT payload if valid, empty dict if invalid
    """
    secret = get_jwt_secret(config)
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
        return True, "", payload
    except jwt.ExpiredSignatureError as e:
        return False, f"JWT Token expired: {e}", {}
    except jwt.InvalidTokenError as e:
        return False, f"Invalid JWT token: {e}", {}
    except Exception as e:
        return False, f"Unexpected error validating JWT: {e}", {}


async def websocket_handler(request):
    """
    WebSocket handler for real-time chat communication.

    Establishes WebSocket connection and handles incoming messages:
    - 'ready': Client signals it's ready to receive messages
    - 'prompt_submission': Client submits form data

    Args:
        request: aiohttp web request object

    Returns:
        WebSocketResponse: Established WebSocket connection
    """
    ws = aiohttp.web.WebSocketResponse()
    await ws.prepare(request)

    # Extract chat_id from query parameters
    bearer_token = request.rel_url.query.get("chat_id")
    if not bearer_token:
        await ws.close(message=b"No chat_id token")
        return ws

    # Validate JWT token for WebSocket connection
    # For websocket, we'll use default config since we don't have access to pipeline config
    is_valid, error_msg, decoded = validate_jwt_token(bearer_token)
    if not is_valid:
        L.warning(f"WebSocket connection rejected: {error_msg}")
        await ws.close(message=b"Invalid or expired token")
        return ws

    chat_id = decoded["chat_id"]

    # Store WebSocket connection for this chat
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
                    # Client signals it's ready to receive messages
                    ws._is_ready = True
                    CHATS[chat_id]["ready_event"].set()

                elif data.get("type") == "prompt_submission":
                    # Client submits form data
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
        # Clean up WebSocket connection
        WEBSOCKETS[chat_id].discard(ws)

    return ws


async def general_proxy(request):
    """
    General proxy endpoint for external resource access.

    Provides a safe way to fetch external resources while preventing
    access to internal/localhost resources.

    Args:
        request: aiohttp web request object

    Returns:
        Response: Proxied content or error response
    """
    target_url = request.query.get("url")
    if not target_url or not re.match(r"^https?://", target_url):
        return aiohttp.web.Response(status=400, text="Invalid or missing URL")

    # Security: Prevent access to internal resources
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


class WebChatFlow:
    """
    Main controller class for managing chat flow interactions.

    This class handles the core chat functionality including:
    - Setting prompts and waiting for user responses
    - Sending messages to users
    - Managing welcome messages
    - Executing registered chat flows
    """

    def __init__(self, event, config=None):
        """
        Initialize WebChatFlow with event data and optional configuration.

        Args:
            event: Event dictionary containing chat context
            config: Optional configuration dictionary
        """
        self.bearer_token = event["bearer_token"]
        self.event = event
        self.config = config

    async def set_prompt(self, fields: list[PromptFormBaseField]) -> dict:
        """
        Set a prompt form and wait for user submission.

        Args:
            fields: List of form fields to display

        Returns:
            dict: Submitted form data from user

        Raises:
            Various JWT-related exceptions if token validation fails
        """
        try:
            chat_id = decode_chat_token(self.bearer_token, self.config)
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError) as e:
            L.error(f"Failed to decode JWT token in set_prompt: {e}")
            raise

        chat_data = CHATS[chat_id]

        # Wait until the WebSocket is ready = someone sent the "ready" message
        await chat_data["ready_event"].wait()

        # Create future to wait for user response
        future = asyncio.get_event_loop().create_future()
        prompt_html = WebChatPromptForm(fields).get_html(
            template_env=WebChatTemplateEnv().get_jinja_env()
        )

        # Store current prompt and future
        chat_data["current_prompt"] = prompt_html
        chat_data["_pending_prompt_future"] = future

        # Send prompt to all connected WebSockets
        websockets = WEBSOCKETS.get(chat_id, set())
        for ws in websockets.copy():
            try:
                await ws.send_str(prompt_html)
            except Exception as e:
                WEBSOCKETS[chat_id].discard(ws)
                print(f"WebSocket error for chat_token={chat_id}: {e}")

        # Wait for user response
        submitted_data = await future

        # Show "awaiting" message while processing
        awaiting_html = WebChatPromptForm(
            [], awaiting_text="Awaiting prompt from server..."
        ).get_html(template_env=WebChatTemplateEnv().get_jinja_env())
        chat_data["current_prompt"] = awaiting_html

        # Update all WebSockets with awaiting message
        for ws in websockets.copy():
            try:
                await ws.send_str(awaiting_html)
            except Exception as e:
                WEBSOCKETS[chat_id].discard(ws)
                print(f"WebSocket error for chat_token={chat_id}: {e}")

        # Store chat history
        chat_data["chat_history"].append({"prompt": submitted_data})

        # Create and send response object
        response_obj = WebChatResponse(
            input_html=f"The submitted data: {submitted_data}", user_response=True
        )
        response_html = response_obj.get_html(
            template_env=WebChatTemplateEnv().get_jinja_env()
        )
        chat_data["chat_history"].append({"prompt_response": submitted_data})

        # Send response to all WebSockets
        for ws in websockets.copy():
            try:
                await ws.send_str(response_html)
            except Exception as e:
                WEBSOCKETS[chat_id].discard(ws)
                print(f"WebSocket error for chat_token={chat_id}: {e}")

        return submitted_data

    async def tell_user(self, response_text, is_html: bool = False):
        """
        Tell a message to the user - render as a response.

        Args:
            response_text: Text or HTML content to send
            is_html: Whether the content is HTML (True) or plain text (False)

        Raises:
            Various JWT-related exceptions if token validation fails
        """
        response = WebChatResponse(input_html=response_text, is_html=is_html)
        try:
            chat_id = decode_chat_token(self.bearer_token, self.config)
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError) as e:
            L.error(f"Failed to decode JWT token in tell_user: {e}")
            raise

        chat_data = CHATS[chat_id]

        # Wait for WebSocket client to be ready
        await chat_data["ready_event"].wait()

        websockets = WEBSOCKETS.get(chat_id, set())
        chat_data["chat_history"].append(
            {"response": response_text, "is_html": is_html}
        )

        # Send response to all connected WebSockets
        for ws in list(websockets):
            try:
                await ws.send_str(
                    response.get_html(template_env=WebChatTemplateEnv().get_jinja_env())
                )
            except Exception:
                websockets.discard(ws)

    async def set_welcome_message(self, welcome_text=None, is_html: bool = False):
        """
        Set a welcome message for the chat session.

        Args:
            welcome_text: Welcome message text or HTML
            is_html: Whether the content is HTML (True) or plain text (False)

        Raises:
            Various JWT-related exceptions if token validation fails
        """
        welcome_window = WebChatWelcomeWindow(
            welcome_text=welcome_text, is_html=is_html
        )
        try:
            chat_id = decode_chat_token(self.bearer_token, self.config)
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError) as e:
            L.error(f"Failed to decode JWT token in set_welcome_message: {e}")
            raise

        chat_data = CHATS[chat_id]
        await chat_data["ready_event"].wait()

        websockets = WEBSOCKETS.get(chat_id, set())
        chat_data["welcome_window"] = welcome_window.get_html(
            template_env=WebChatTemplateEnv().get_jinja_env()
        )

        # Send welcome message to all connected WebSockets
        for ws in list(websockets):
            try:
                await ws.send_str(
                    welcome_window.get_html(
                        template_env=WebChatTemplateEnv().get_jinja_env()
                    )
                )
            except Exception:
                websockets.discard(ws)

    async def run_flow(self, flow_name: str):
        """
        Execute a registered chat flow by name.

        Args:
            flow_name: Name of the registered flow to execute

        Raises:
            ValueError: If the specified flow is not registered
        """
        flow_func = WEBCHAT_FLOW_REGISTRY.get(flow_name)
        if not flow_func:
            raise ValueError(f"Flow '{flow_name}' not registered")
        await flow_func(self.event)


def get_event():
    """
    Extract the 'event' parameter from the caller's frame.

    This function inspects the call stack to find the event parameter
    that was passed to the calling function.

    Returns:
        dict: Event dictionary from caller

    Raises:
        RuntimeError: If event parameter cannot be found
    """
    frame = inspect.currentframe().f_back
    caller_locals = frame.f_locals

    if "event" in caller_locals:
        event = caller_locals["event"]
    else:
        parent_frame = frame.f_back
        if parent_frame and "event" in parent_frame.f_locals:
            event = parent_frame.f_locals["event"]
        else:
            raise RuntimeError("Could not find event parameter")
    return event


async def run_flow(flow_name: str):
    """
    Execute a registered chat flow by name (standalone function for running of the first flow).

    Args:
        flow_name: Name of the registered flow to execute

    Raises:
        ValueError: If the specified flow is not registered
    """
    event = get_event()
    flow_func = WEBCHAT_FLOW_REGISTRY.get(flow_name)
    if not flow_func:
        raise ValueError(f"Flow '{flow_name}' not registered")
    await flow_func(event)


def create_webchat_flow(name: str):
    """
    Decorator to register a function as a WebChat flow.

    Args:
        name: Name to register the flow under

    Returns:
        function: Decorated function
    """

    def decorator(func):
        async def wrapper(event):
            chat = _create_webchat_flow()
            return await func(chat)

        WEBCHAT_FLOW_REGISTRY[name] = wrapper
        return wrapper

    return decorator


def _create_webchat_flow():
    """
    Internal function to create a WebChatFlow instance.

    Attempts to extract configuration from the pipeline context.

    Returns:
        WebChatFlow: Configured chat flow instance
    """
    event = get_event()
    # Try to get config from the pipeline context
    config = None
    try:
        # Look for config in the event or try to get it from the pipeline
        if "config" in event:
            config = event["config"]
        elif "pipeline" in event:
            config = event["pipeline"].Config
    except (KeyError, AttributeError):
        pass

    chat = WebChatFlow(event, config)
    return chat


class WebChatServerConnection(Connection):
    """
    Connection class for the WebChat HTTP server.

    Manages the aiohttp web application, template loading, and route registration.
    """

    ConfigDefaults = {
        "port": 8080,
        "max_body_size_bytes": 1024 * 1024 * 1000,  # 1GB default
    }

    def __init__(self, app, id=None, config=None):
        """
        Initialize the WebChat server connection.

        Args:
            app: BSPump application instance
            id: Connection identifier
            config: Configuration dictionary
        """
        super().__init__(app, id=id, config=config)

        # Create aiohttp application with configured body size limit
        self.aiohttp_app = aiohttp.web.Application(
            client_max_size=int(self.Config["max_body_size_bytes"])
        )

        # Setup template environment
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        aiohttp_jinja2.setup(
            self.aiohttp_app,
            loader=jinja2.FileSystemLoader(os.path.join(self.base_dir, "templates")),
        )

        # Setup routing
        router = self.aiohttp_app.router
        if _registered_endpoints:
            for route, handler in _registered_endpoints.items():
                router.add_route("*", route, handler)
        router.add_get("/ws", websocket_handler)
        router.add_get("/api/proxy", general_proxy)
        router.add_get("/new-chat", new_chat_handler)

        # Setup static file serving
        self.aiohttp_app.router.add_static(
            "/static", os.path.join(self.base_dir, "static")
        )

        # Start the server
        self.start_server()

    def start_server(self):
        """Start the HTTP server in the background."""
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

    This class provides the base functionality for HTTP-based chat sources,
    handling request processing and pipeline integration.
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
        """
        Initialize the WebChat route source.

        Args:
            app: BSPump application instance
            pipeline: Pipeline instance
            connection: Connection identifier
            method: HTTP method to handle
            route: URL route to handle
            id: Source identifier
            config: Configuration dictionary
        """
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

                # Create default connection if none exists
                self.Connection = WebChatServerConnection(
                    app,
                    "DefaultWebServerConnection",
                    {"port": default_port},
                )
                app.PumpService.add_connection(self.Connection)

        self.aiohttp_app = self.Connection.aiohttp_app
        self.aiohttp_app.router.add_route(method, route, self.handle_request)

    async def main(self):
        """Main source method - not used for HTTP sources."""
        pass

    async def handle_request(self, request):
        """
        Handle incoming HTTP requests.

        Args:
            request: aiohttp web request object

        Returns:
            Response: HTTP response object
        """
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
            L.exception(f"Exception in WebChatSource handle_request: {e}")
            # Return a more informative error response
            return aiohttp.web.Response(
                text=f"Internal Server Error: {str(e)}",
                status=500,
                content_type="text/plain",
            )


async def new_chat_handler(request):
    """
    Handler for creating new chat sessions.

    Generates a new chat ID and JWT token, then redirects to the chat interface.

    Args:
        request: aiohttp web request object

    Returns:
        HTTPFound: Redirect response to new chat
    """
    chat_id = generate_session_id()
    token = generate_bearer_token(chat_id)
    CHATS[chat_id] = {
        "chat_history": [],
        "current_prompt": None,
        "ready_event": asyncio.Event(),
        "started": False,
        "bearer_token": token,
        "welcome_window": "",
    }
    raise aiohttp.web.HTTPFound(f"/?chat_id={token}")


class WebChatSource(WebChatRouteSource):
    """
    Main WebChat source component for handling chat requests.

    Extends WebChatRouteSource with chat-specific functionality including
    session management, JWT validation, and chat interface rendering.
    """

    def __init__(
        self,
        app,
        pipeline,
        connection="DefaultWebServerConnection",
        route="/",
        id=None,
        config=None,
    ):
        """
        Initialize the WebChat source.

        Args:
            app: BSPump application instance
            pipeline: Pipeline instance
            connection: Connection identifier
            route: URL route to handle
            id: Source identifier
            config: Configuration dictionary
        """
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

    async def serve_index(
        self, request: aiohttp.web.Request, bearer_token
    ) -> aiohttp.web.Response:
        """
        Serve the main chat interface page.

        Args:
            request: aiohttp web request object
            bearer_token: JWT token for authentication

        Returns:
            Response: Rendered HTML page
        """
        template_env = WebChatTemplateEnv().get_jinja_env()

        chat_data = CHATS[decode_chat_token(bearer_token)]

        # Build chat history HTML
        chat_history_html = ""
        for item in chat_data["chat_history"]:
            if "response" in item:
                is_html = item.get("is_html", False)
                html = WebChatResponse(
                    input_html=item["response"], is_html=is_html
                ).get_html(template_env=template_env)
            elif "prompt_response" in item:
                html = WebChatResponse(
                    input_html=item["prompt_response"], user_response=True
                ).get_html(template_env=template_env)
            else:
                continue
            chat_history_html += html

        # Get current prompt and welcome message
        current_prompt_html = chat_data.get("current_prompt", "")
        welcome_html = chat_data.get("welcome_window", "")

        # Prepare template context
        context = {
            "bearer_token": bearer_token,
            "current_prompt_html": current_prompt_html,
            "chat_history_html": chat_history_html,
            "welcome_html": welcome_html,
            "chats": [
                {"chat_id": chat_id, "token": CHATS[chat_id]["bearer_token"]}
                for chat_id in CHATS.keys()
            ],
        }

        # Start pipeline processing if not already started
        if not chat_data.get("started"):
            await self.pipeline.process({"bearer_token": bearer_token})
            chat_data["started"] = True

        return aiohttp_jinja2.render_template("index.html", request, context)

    async def handle_request(
        self, request: aiohttp.web.Request
    ) -> aiohttp.web.Response:
        """
        Handle incoming chat requests.

        Manages chat session creation, JWT validation, and page rendering.

        Args:
            request: aiohttp web request object

        Returns:
            Response: HTTP response object
        """
        if request.method != "GET":
            return aiohttp.web.Response(status=405)

        # Extract and validate JWT token
        token = request.query.get("chat_id")
        if not token:
            # Create new chat session if no token provided
            chat_id = str(uuid.uuid4())
            token = generate_bearer_token(chat_id)
            print(f"Generated NEW token for new chat_id={chat_id}: {token}")
            location = f"/?chat_id={token}"
            raise aiohttp.web.HTTPFound(location)

        try:
            # Validate existing token
            secret = get_jwt_secret(
                self.pipeline.Config if hasattr(self, "pipeline") else None
            )
            payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
            chat_id = payload.get("chat_id")
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as e:
            # Create new session if token is invalid/expired
            print(f"Invalid or expired token: {e}")
            chat_id = str(uuid.uuid4())
            token = generate_bearer_token(chat_id)
            print(f"Generated NEW token for new chat_id={chat_id}: {token}")
            location = f"/?chat_id={token}"
            raise aiohttp.web.HTTPFound(location)

        # Initialize chat session if it doesn't exist
        if chat_id not in CHATS:
            CHATS[chat_id] = {
                "chat_history": [],
                "current_prompt": None,
                "ready_event": asyncio.Event(),
                "started": False,
                "bearer_token": token,
                "welcome_window": "",
            }
            print(f"Initialized chat store for chat_id={chat_id}")

        return await self.serve_index(request, bearer_token=token)


class WebchatSink(Sink):
    """
    Sink component for WebChat responses.

    Handles setting response futures to complete HTTP requests.
    """

    def process(self, context, item):
        """
        Process items and set response futures.

        Args:
            context: Processing context
            item: Item to process
        """
        response_future = item.get("response_future")
        if response_future and not response_future.done():
            response_future.set_result(aiohttp.web.Response(status=204))
