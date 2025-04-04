import aiohttp.web

from bspump.http_webchat.api.api_endpoints import get_fund_info, get_welcome_message, get_prompt_input, \
    get_web_chat_response

from bspump.http_webchat.server.app import app, set_app, WebChat

if __name__ == "__main__":
    webchat = WebChat({
        "/api/fund" : get_fund_info,
        "/api/welcome_message" : get_welcome_message,
        "/api/prompt_input" : get_prompt_input,
        "/api/response_box" : get_web_chat_response
    })