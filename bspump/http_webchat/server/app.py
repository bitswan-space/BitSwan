import json
from typing import Callable, List

import aiohttp.web
import aiohttp_jinja2
import jinja2
import os

from jinja2 import Environment

app = aiohttp.web.Application()

class WebChatTemplateEnv:
    def __init__(self, extra_template_dir:str=None):
        """
        Creates template environment on user side that will be then used for creating other components
        :param extra_template_dir: path to template directory, could be none, because use can specify the templates as strings
        """
        self.extra_template_dir = extra_template_dir
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.template_env = self.create_template_env()

    def create_template_env(self) -> Environment:
        main_template_dir = os.path.join(self.base_dir, 'templates')
        loader_paths = []

        if not os.path.isdir(main_template_dir):
            raise ValueError(f"Template directory '{main_template_dir}' does not exist")
        loader_paths.append(main_template_dir)

        if self.extra_template_dir:
            loader_paths.append(self.extra_template_dir)

        aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(loader_paths))

        template_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(loader_paths),
            autoescape=jinja2.select_autoescape(['html', 'xml'])
        )

        return template_env

    def get_jinja_env(self) -> Environment:
        """
        :return: Environment variable
        """
        return self.template_env

class FormInput:
    def __init__(self, label:str, name:str, input_type:str, step:float | int =None, required=False):
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
            'response_box_api': self.submit_api_call,
            'form_inputs': self.form_inputs
        }
        return context

    def get_html(self, template_env: Environment) -> str:
        template = template_env.get_template('components/prompt-box.html')
        return template.render(self.get_context())

class WebChatWelcomeWindow:
    def __init__(self, welcome_text: str, prompt_form:WebChatPromptForm):
        """
        Class for defining of the first window that is rendered and is visible all the time
        :param welcome_text: text or html string that should be rendered
        :param prompt_form: html of the prompt that is rendered with the window
        """
        self.welcome_text = welcome_text or ""
        self.prompt_form = prompt_form

    def get_context(self, template_env: Environment) -> dict:
        context = {
            'welcome_text': self.welcome_text,
        }
        if self.prompt_form:
            context['prompt_html'] = self.prompt_form.get_html(template_env)
        return context

    def get_html(self, template_env: Environment) -> str:
        template = template_env.get_template('components/welcome-message-box.html')
        return template.render(self.get_context(template_env))

class WebChatResponse:
    def __init__(self, input_html: str, prompt_form:WebChatPromptForm=None, api_endpoint:str=None):
        """

        :param input_html:
        :param prompt_form:
        :param api_endpoint:
        """
        self.input_html = input_html or ""
        self.prompt_form = prompt_form
        self.api_endpoint = api_endpoint

    def get_context(self, template_env: Environment) -> dict:
        return {
            'response_text': self.input_html,
            'prompt_html': self.prompt_form.get_html(template_env) if self.prompt_form else "",
            'api_endpoint': self.api_endpoint if self.api_endpoint else "",
            'has_prompt': bool(self.prompt_form),
        }

    def get_html(self, template_env: Environment) -> str:
        if self.api_endpoint:
            template = template_env.get_template('components/web-chat-response-with-request.html')
        else:
            template = template_env.get_template('components/web-chat-response.html')
        return template.render(self.get_context(template_env))


class WebChatResponseSequence:
    def __init__(self, responses: List[WebChatResponse]):
        self.responses = responses

    def get_html(self, template_env: Environment) -> str:
        rendered_responses = [response.get_html(template_env) for response in self.responses]
        js_safe_responses = json.dumps(rendered_responses)
        context = {
            'responses': js_safe_responses,
        }
        template = template_env.get_template('components/web-chat-sequence-response.html')
        return template.render(context)

async def mock_endpoint(request):
    return aiohttp.web.Response(text="")  # or JSON if needed


# webchat creates the server and add the endpoints
class WebChat:
    def __init__(self, welcome_message_api: tuple[str, Callable], prompt_response_api: tuple[str, Callable]):
        self.welcome_message_api = welcome_message_api
        self.prompt_response_api = prompt_response_api
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.set_app()
        app.add_routes([
            aiohttp.web.get(welcome_message_api[0], welcome_message_api[1]),
            aiohttp.web.route('*', prompt_response_api[0], prompt_response_api[1]),
        ])
        app.router.add_post('/api/mock', mock_endpoint)
        aiohttp.web.run_app(app, host="127.0.0.1", port=8082)

    async def serve_index(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        # these api endpoints are set in api code
        context = {
            'welcome_message_api': self.welcome_message_api[0],
            'response_box_api': self.prompt_response_api[0],
        }
        return aiohttp_jinja2.render_template('index.html', request, context)

    def set_app(self):
        app.add_routes([aiohttp.web.static("/static", os.path.join(self.base_dir, './static'))])
        app.add_routes([
            aiohttp.web.get("/", self.serve_index)
        ])

# Chat Response by mohol zmenit prompt, prompt bude disabled pokym mu nepride
# Force people that prompt can be only form
