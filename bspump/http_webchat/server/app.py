import aiohttp.web
import aiohttp_jinja2
import jinja2
import os

async def serve_index(request):
    context = {
        'welcome_message': '/api/welcome_message',
        'prompt_input': '/api/prompt_input'
    }
    return aiohttp_jinja2.render_template('index.html', request, context)

async def get_fund_info(request):
    fund_id = request.query.get('fund_id')

    if not fund_id:
        return aiohttp.web.json_response({"error": "Missing fund_id"}, status=400)

    fund_info = {
        "fund_id": fund_id,
        "name": "Sample Fund",
        "balance": 100000,
    }

    return aiohttp.web.json_response(fund_info)

async def get_welcome_message(request):
    return aiohttp_jinja2.render_template("welcome-message.html", request, {})

async def get_prompt_input(request):
    return aiohttp_jinja2.render_template("prompt-input.html", request, {})

app = aiohttp.web.Application()
template_dirs = [
    'templates',
    os.path.abspath(os.path.join(os.path.dirname(__file__), '../api'))
]

aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(template_dirs))

app.add_routes([
    aiohttp.web.get("/", serve_index),
    aiohttp.web.get("/api/fund", get_fund_info),
    aiohttp.web.get("/api/welcome_message", get_welcome_message),
    aiohttp.web.get("/api/prompt_input", get_prompt_input)
])

app.add_routes([aiohttp.web.static("/static", './static')])

if __name__ == "__main__":
    aiohttp.web.run_app(app, host="127.0.0.1", port=8080)
