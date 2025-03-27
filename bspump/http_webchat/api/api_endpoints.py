import aiohttp.web
import aiohttp_jinja2
import os

from bspump.http_webchat.api.template_env import template_env
from bspump.http_webchat.server.app import WebChatResponse

base_dir = os.path.dirname(os.path.abspath(__file__))
async def get_welcome_message(request):
    return aiohttp_jinja2.render_template('welcome-message.html', request, {})

async def get_prompt_input(request):
    context = {
        'prompt_input_api': '/api/prompt_input',
        'response_box_api': '/api/response_box'
    }
    return aiohttp_jinja2.render_template('prompt-input.html', request, context)

async def get_web_chat_response(request):
    fund_id = request.query.get('fund_id')

    if not fund_id:
        return aiohttp.web.json_response({"error": "Missing fund_id"}, status=400)

    if fund_id == "123":
        return await get_response_123()
    elif fund_id == "12":
        return await get_response_12()
    else:
        webchat = WebChatResponse(response_text=f"Calculating odkupy for Fund {fund_id}")
        rendered_html = webchat.render_response(template_env)
        return aiohttp.web.Response(text=rendered_html, content_type='text/html')

async def get_response_123():
    calculating = WebChatResponse(response_text=f"Calculating odkupy for Fund {123}")
    result = WebChatResponse(response_text=f"Total valuation is 2 300 345 CZK.")
    next_message = WebChatResponse(response_text=f"Please pick another fund for calculation.")

    rendered_html = calculating.render_response(template_env) + result.render_response(template_env) + next_message.render_response(template_env)
    return aiohttp.web.Response(text=rendered_html, content_type='text/html')

async def get_response_12():
    webchat = WebChatResponse(response_text=f"Calculating odkupy for Fund {12}")
    rendered_html = webchat.render_response(template_env)
    return aiohttp.web.Response(text=rendered_html, content_type='text/html')


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