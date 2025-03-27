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

class WebChatResponse:
    def __init__(self, response_text=None):
        self.response_text = response_text or ""
        self.styling = "bg-white shadow-md rounded-xl rounded-tr-none w-[90%] px-8 py-6 flex items-center border border-gray-300"

    def get_context(self):
        return {
            'response_text': self.response_text,
            'styling': self.styling
        }

    def render_response(self, template_env):
        template = template_env.get_template('components/web-chat-response.html')
        return template.render(self.get_context())


async def serve_index(request):
    context = {
        'welcome_message_api': '/api/welcome_message',
        'prompt_input_api': '/api/prompt_input',
        'response_box_api': '/api/response_box'
    }
    print("context", context)
    return aiohttp_jinja2.render_template('index.html', request, context)

def set_app():
    app.add_routes([aiohttp.web.static("/static", os.path.join(base_dir, './static'))])
    app.add_routes([
        aiohttp.web.get("/", serve_index)
    ])


