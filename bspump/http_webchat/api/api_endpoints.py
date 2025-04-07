import aiohttp.web
import aiohttp_jinja2
import os

from bspump.http_webchat.api.template_env import template_env
from bspump.http_webchat.server.app import WebChatResponse, WebChatWelcomeWindow, WebchatPrompt

base_dir = os.path.dirname(os.path.abspath(__file__))

# /api/welcome_message
async def get_welcome_message(request):
    welcome_message = WebChatWelcomeWindow(input_html="Hello, welcome to the odkupy calculation assistant. Please select the fond you would like to calculate odkupy for.")
    return aiohttp.web.Response(text=welcome_message.get_html(), content_type='text/html')

# /api/prompt_input -> change this endpoint if you want to change the input
async def get_prompt_input(request):
    context = {
        'prompt_input_api': '/api/prompt_input',
        'response_box_api': '/api/response_box'
    }

    rendered_html = aiohttp_jinja2.render_string('prompt-input.html', request, context)
    prompt = WebchatPrompt(input_html=rendered_html)

    return aiohttp.web.Response(text=prompt.get_html(), content_type='text/html')

# /api/response_box
async def get_web_chat_response(request):
    fund_id = request.query.get('fund_id')

    if not fund_id:
        return aiohttp.web.json_response({"error": "Missing fund_id"}, status=400)

    if fund_id == "123":
        return await get_response_123()
    elif fund_id == "12":
        return await get_response_12()
    else:
        webchat = WebChatResponse(input_html=f"Calculating odkupy for Fund {fund_id}")
        return aiohttp.web.Response(text=webchat.get_html(template_env), content_type='text/html')

async def get_response_123():
    # TODO not return the response in one
    calculating = WebChatResponse(input_html=f"Calculating odkupy for Fund {123}")
    result = WebChatResponse(input_html=f"Total valuation is 2 300 345 CZK.")
    next_message = WebChatResponse(input_html=f"Please pick another fund for calculation.")

    rendered_html = calculating.get_html(template_env) + result.get_html(template_env) + next_message.get_html(template_env)
    return aiohttp.web.Response(text=rendered_html, content_type='text/html')

async def get_response_12():
    webchat = WebChatResponse(input_html=f"Calculating odkupy for Fund {12}")
    return aiohttp.web.Response(text=webchat.get_html(template_env), content_type='text/html')
