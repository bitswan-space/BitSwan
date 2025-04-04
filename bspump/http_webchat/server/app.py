from typing import Dict, Callable

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
# prompt iw just one and is rendered on loading
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

class WebchatPrompt:
    def __init__(self, input_html=None):
        self.input_html = input_html or ""

    def get_context(self):
        return {
            'prompt_html': self.input_html,
        }

    def get_html(self):
        return self.input_html


class WebChatResponse:
    def __init__(self, input_html=None):
        self.input_html = input_html or ""
        self.styling = "bg-white shadow-md rounded-xl rounded-tr-none w-[90%] px-8 py-6 flex items-center border border-gray-300"

    def get_context(self):
        return {
            'response_text': self.input_html,
            'response_styling': self.styling
        }

    def get_html(self, template_env):
        template = template_env.get_template('components/web-chat-response.html')
        return template.render(self.get_context())

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
