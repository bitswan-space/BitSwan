import aiohttp.web

from bspump.http_webchat.api.api_endpoints import get_fund_info, get_welcome_message, get_prompt_input, get_web_chat_response

from bspump.http_webchat.server.app import app, set_app

set_app()
app.add_routes([
    aiohttp.web.get("/api/fund", get_fund_info),
    aiohttp.web.get("/api/welcome_message", get_welcome_message),
    aiohttp.web.get("/api/prompt_input", get_prompt_input),
    aiohttp.web.get("/api/response_box", get_web_chat_response)
])

if __name__ == "__main__":
    aiohttp.web.run_app(app, host="127.0.0.1", port=8080)