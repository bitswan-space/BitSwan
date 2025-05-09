import json
from typing import Callable, List, Union

import aiohttp.web
import aiohttp_jinja2
import jinja2
import os

app = aiohttp.web.Application()
base_dir = os.path.dirname(os.path.abspath(__file__))

def create_template_env(extra_template_dir=None):
    main_template_dir = os.path.join(base_dir, 'templates')
    loader_paths = []

    if not os.path.isdir(main_template_dir):
        raise ValueError(f"Template directory '{main_template_dir}' does not exist")
    loader_paths.append(main_template_dir)

    if extra_template_dir:
        if os.path.isdir(extra_template_dir):
            loader_paths.append(extra_template_dir)
        else:
            raise ValueError(f"Extra template directory '{extra_template_dir}' does not exist")

    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(loader_paths))

    template_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(loader_paths),
        autoescape=jinja2.select_autoescape(['html', 'xml'])
    )

    return template_env

# WebchatWelcomeWindow and PromptInput returns just the input html
# WebChatResponse returns whole rendered html because user can create how many responses they want but welcome window and
# prompt is just one and is rendered on loading
# Welcome window and prompt templates use api calls in templates to get the html they should render
# There are no api calls in response templates because they are in the button in prompt template
class WebChatWelcomeWindow:
    def __init__(self, input_html=None):
        self.input_html = input_html or ""

    def get_context(self):
        return {
            'welcome_text': self.input_html,
        }

    def get_html(self):
        return self.input_html

class WebChatResponse:
    def __init__(self, input_html=None, api_endpoint=None):
        self.input_html = input_html or ""
        self.api_endpoint = api_endpoint

    def get_context(self):
        context = {
            'response_text': self.input_html,
        }
        if self.api_endpoint:
            context['api_endpoint'] = self.api_endpoint
        return context

    def get_html(self, template_env):
        if self.api_endpoint:
            template = template_env.get_template('components/web-chat-response-with-request.html')
        else:
            template = template_env.get_template('components/web-chat-response.html')
        return template.render(self.get_context())

class WebChatResponseWithPrompt(WebChatResponse):
    def __init__(self, input_html=None, prompt_html=None, api_endpoint=None):
        super().__init__(input_html, api_endpoint)
        self.prompt_html = prompt_html

    def get_context(self):
        context = super().get_context()
        context['prompt_html'] = self.prompt_html
        return context

    def get_html(self, template_env):
        rendered_html = super().get_html(template_env)
        response_with_prompt_html = rendered_html.replace('id="webchat_response"', 'id="response-with-prompt"', 1)
        return response_with_prompt_html

class WebChatResponseSequence:
    def __init__(self, responses: List[Union[WebChatResponse, WebChatResponseWithPrompt]]):
        self.responses = responses

    def get_html(self, template_env):
        rendered_responses = [response.get_html(template_env) for response in self.responses]
        js_safe_responses = json.dumps(rendered_responses)
        context = {
            'responses': js_safe_responses,
        }
        template = template_env.get_template('components/web-chat-sequence-response.html')
        return template.render(context)

class FormInput:
    def __init__(self, label, name, input_type, step=None, required=False):
        self.label = label
        self.name = name
        self.input_type = input_type
        self.step = step
        self.required = required

# you are able to change the endpoint
class WebChatPromptForm:
    def __init__(self, form_inputs: List[FormInput], submit_api_call):
        self.form_inputs = form_inputs
        self.submit_api_call = submit_api_call

    def get_context(self):
        context = {
            'response_box_api': self.submit_api_call,
            'form_inputs': self.form_inputs
        }
        return context

    def get_html(self, template_env):
        template = template_env.get_template('components/prompt-box.html')
        return template.render(self.get_context())


# webchat creates the server and add the endpoints
class WebChat:
    def __init__(self, welcome_message_api: tuple[str, Callable], prompt_input_api: tuple[str, Callable], prompt_response_api: tuple[str, Callable]):
        self.welcome_message_api = welcome_message_api
        self.prompt_input_api = prompt_input_api
        self.prompt_response_api = prompt_response_api
        self.set_app()
        app.add_routes([
            aiohttp.web.get(welcome_message_api[0], welcome_message_api[1]),
            aiohttp.web.get(prompt_input_api[0],prompt_input_api[1]),
            aiohttp.web.get(prompt_response_api[0],prompt_response_api[1])
        ])
        aiohttp.web.run_app(app, host="127.0.0.1", port=8080)

    async def serve_index(self, request):
        # these api endpoints are set in api code
        context = {
            'welcome_message_api': self.welcome_message_api[0],
            'prompt_input_api': self.prompt_input_api[0],
            'response_box_api': self.prompt_response_api[0],
        }
        return aiohttp_jinja2.render_template('index.html', request, context)

    def set_app(self):
        app.add_routes([aiohttp.web.static("/static", os.path.join(base_dir, './static'))])
        app.add_routes([
            aiohttp.web.get("/", self.serve_index)
        ])

# Chat Response by mohol zmenit prompt, prompt bude disabled pokym mu nepride
# Force people that prompt can be only form?