import aiohttp.web
import aiohttp_jinja2
import jinja2
import os
from bspump.http_webchat.api.endpoints import get_welcome_message, get_fund_info, get_prompt_input, get_web_chat_response

async def serve_index(request):
    context = {
        'welcome_message': '/api/welcome_message',
        'prompt_input': '/api/prompt_input',
        'response_box': '/api/response_box'
    }
    return aiohttp_jinja2.render_template('index.html', request, context)

app = aiohttp.web.Application()

base_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(base_dir, 'templates')
if not os.path.isdir(template_dir):
    raise ValueError(f"Template directory '{template_dir}' does not exist")

api_dir = os.path.abspath(os.path.join(base_dir, '../api/templates'))
if not os.path.isdir(api_dir):
    raise ValueError(f"Template directory '{api_dir}' does not exist")

template_dirs = [
    template_dir,
    api_dir
]

aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(template_dirs))

app.add_routes([
    aiohttp.web.get("/", serve_index),
    aiohttp.web.get("/api/fund", get_fund_info),
    aiohttp.web.get("/api/welcome_message", get_welcome_message),
    aiohttp.web.get("/api/prompt_input", get_prompt_input),
    aiohttp.web.get("/api/response_box", get_web_chat_response)
])

app.add_routes([aiohttp.web.static("/static", os.path.join(base_dir, './static'))])
if __name__ == "__main__":
    aiohttp.web.run_app(app, host="127.0.0.1", port=8080)
