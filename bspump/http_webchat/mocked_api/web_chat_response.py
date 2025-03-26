import aiohttp.web

async def get_web_chat_response(request):
    response_data = {
        "message": "Welcome to the API!"
    }
    return aiohttp.web.json_response(response_data)