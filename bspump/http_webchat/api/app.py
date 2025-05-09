import os

from bspump.http_webchat.api.api_endpoints import get_welcome_message, \
    get_web_chat_response

from bspump.http_webchat.server.app import WebChat

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    api_dir = os.path.abspath(os.path.join(base_dir, 'templates'))
    webchat = WebChat(welcome_message_api=("/api/welcome_message", get_welcome_message),
                      prompt_response_api=( "/api/response_box", get_web_chat_response))