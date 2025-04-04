import aiohttp.web

from bspump.http_webchat.api.api_endpoints import get_welcome_message, get_prompt_input, \
    get_web_chat_response

from bspump.http_webchat.server.app import WebChat

if __name__ == "__main__":
    webchat = WebChat(welcome_message_api=("/api/welcome_message", get_welcome_message),
                      prompt_input_api=("/api/prompt_input", get_prompt_input),
                      prompt_response_api=( "/api/response_box", get_web_chat_response))