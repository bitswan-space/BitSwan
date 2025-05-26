import asyncio
import importlib.util
import json
import re
import time
from pathlib import Path
from typing import Callable, List, Optional

import aiohttp.web
import aiohttp_jinja2
import jinja2
import os

from nbformat import read
from nbconvert.preprocessors import ExecutePreprocessor
import aiohttp.web

from jinja2 import Environment

app = aiohttp.web.Application()


class WebChatTemplateEnv:
    def __init__(self, extra_template_dir: str = None):
        """
        Creates template environment on user side that will be then used for creating other components
        :param extra_template_dir: path to template directory, could be none, because use can specify the templates as strings
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
            "form_id": f"prompt-form-{int(time.time() * 1000)}"
        }
        return context

    def get_html(self, template_env: Environment) -> str:
        template = template_env.get_template("components/prompt-box.html")
        return template.render(self.get_context())


class WebChatWelcomeWindow:
    def __init__(self, welcome_text: str, prompt_form: WebChatPromptForm, endpoint_route: str):
        """
        Class for defining the first window that is rendered and is visible all the time
        :param welcome_text: text or html string that should be rendered
        :param prompt_form: html of the prompt that is rendered with the window
        :param endpoint_route: API endpoint route that will serve the welcome message HTML
        """
        self.welcome_text = welcome_text or ""
        self.prompt_form = prompt_form
        self.endpoint_route = endpoint_route or ""

    def get_context(self, template_env: Environment) -> dict:
        context = {
            "welcome_text": self.welcome_text,
            "welcome_endpoint": self.get_endpoint_route(),
        }
        if self.prompt_form:
            context["prompt_html"] = self.prompt_form.get_html(template_env)
        return context

    def get_html(self, template_env: Environment) -> str:
        template = template_env.get_template("components/welcome-message-box.html")
        return template.render(self.get_context(template_env))

    def get_endpoint_route(self) -> str:
        return self.endpoint_route


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

_registered_endpoints_notebooks: dict[str, str] = {}
_registered_endpoints: dict[str, Callable] = {}

def find_module_path(module_name):
    spec = importlib.util.find_spec(module_name)
    if spec and spec.origin:
        return spec.origin
    else:
        return f"Module '{module_name}' not found or built-in."

base_path = str(
    Path(os.path.split(find_module_path("bspump"))[:-1][0])
    / "http_webchat"
    / "server"
)

ENDPOINTS_FILE = os.path.join(base_path, "endpoints.json")
def load_registered_endpoints():
    global _registered_endpoints_notebooks
    if os.path.exists(ENDPOINTS_FILE):
        if os.path.getsize(ENDPOINTS_FILE) > 0:
            with open(ENDPOINTS_FILE, "r") as f:
                _registered_endpoints_notebooks = json.load(f)
        else:
            _registered_endpoints_notebooks = {}
    else:
        _registered_endpoints_notebooks = {}


def save_registered_endpoints():
    with open(ENDPOINTS_FILE, "w") as f:
        json.dump(_registered_endpoints_notebooks, f, indent=2)

def register_endpoint(
    route: str,
    *,
    handler: Optional[Callable] = None,
    notebook_name: Optional[str] = None
):
    if notebook_name:
        cwd = os.getcwd()
        notebook_path = os.path.join(cwd, notebook_name)
        load_registered_endpoints()
        for existing_route, _ in _registered_endpoints_notebooks.items():
            if existing_route == route:
                print(f"[WebChat] Skipping duplicate route: {route}")
                return
        _registered_endpoints_notebooks[route] = notebook_path
        save_registered_endpoints()
        print(f"[WebChat] Registered: {route} -> {notebook_path}")

    else:
        _registered_endpoints[route] = handler

async def notebook_handler(request, notebook_path: str):
    nb = read(open(notebook_path), as_version=4)
    ep = ExecutePreprocessor(timeout=60, kernel_name='python3')

    try:
        ep.preprocess(nb, {'metadata': {'path': os.path.dirname(notebook_path)}})
    except Exception as e:
        return aiohttp.web.Response(status=500, text=f"Notebook error: {str(e)}")

    # Shared execution context
    exec_context = {}

    try:
        for cell in nb.cells:
            if cell.cell_type == "code":
                exec(cell.source, exec_context)
    except Exception as e:
        return aiohttp.web.Response(status=500, text=f"Error in exec: {e}")

    html_output = exec_context.get("html_output", "")

    return aiohttp.web.Response(text=html_output, content_type="text/html")


def make_dynamic_handler(notebook_path):
    async def dynamic_handler(request):
        return await notebook_handler(request, notebook_path)

    return dynamic_handler


class WebChat:
    def __init__(
        self,
        welcome_message_api: str,
        prompt_response_api: str,
    ):
        self.welcome_message_api = welcome_message_api
        self.prompt_response_api = prompt_response_api
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.app = aiohttp.web.Application()
        aiohttp_jinja2.setup(
            self.app,
            loader=jinja2.FileSystemLoader(os.path.join(self.base_dir, "templates"))
        )
        self.set_app()
        self.register_routes()

        # Attributes to hold runner and background task
        self._runner = None
        self._site = None
        self._server_task = None

    def set_app(self):
        self.app.router.add_static("/static", os.path.join(self.base_dir, "static"))
        self.app.router.add_get("/", self.serve_index)

    def register_routes(self):
        if _registered_endpoints:
            for route, handler in _registered_endpoints.items():
                self.app.router.add_route("*", route, handler)
        if _registered_endpoints_notebooks:
            for route, notebook_path in _registered_endpoints_notebooks.items():
                self.app.router.add_route("*", route, make_dynamic_handler(notebook_path))
        self.app.router.add_get("/api/proxy", general_proxy)

    async def serve_index(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        context = {
            "welcome_message_api": self.welcome_message_api,
            "response_box_api": self.prompt_response_api,
        }
        return aiohttp_jinja2.render_template("index.html", request, context)

    def run(self, host="127.0.0.1", port=8080):
        aiohttp.web.run_app(self.app, host=host, port=port)

    async def _start_runner(self, host="127.0.0.1", port=8080):
        self._runner = aiohttp.web.AppRunner(self.app)
        await self._runner.setup()
        self._site = aiohttp.web.TCPSite(self._runner, host=host, port=port)
        await self._site.start()
        print(f"Server started at http://{host}:{port}")
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            print("Server is shutting down...")
            await self._runner.cleanup()

    def start_webchat(self, host="127.0.0.1", port=8080):
        """
        Start the aiohttp server as a background task.
        Use this in Jupyter or async environment.
        """
        if self._server_task is None or self._server_task.done():
            self._server_task = asyncio.create_task(self._start_runner(host, port))
        else:
            print("Server is already running.")

    async def stop_webchat(self):
        """
        Stop the aiohttp server and cleanup.
        Use `await` to stop the server cleanly.
        """
        if self._server_task and not self._server_task.done():
            self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                print("Server task cancelled and cleaned up.")
        else:
            print("Server is not running or already stopped.")
