import bspump
import aiohttp.web

from bspump.http_webchat.server.server import WebChat


class WebChatSource(bspump.Source):
    def __init__(self, app, pipeline, welcome_message_api, prompt_response_api, id=None, config=None):
        super().__init__(app, pipeline, id=id, config=config)
        self.Site = None
        self.Runner = None
        self.WelcomeAPI = welcome_message_api
        self.ResponseAPI = prompt_response_api

        self.WebChat = WebChat(
            welcome_message_api=self.WelcomeAPI,
            prompt_response_api=self.ResponseAPI,
        )

        # Add custom route to handle chat input
        self.WebChat.app.router.add_post("/api/chat", self.handle_chat)

    async def handle_chat(self, request):
        try:
            data = await request.json()
        except Exception:
            return aiohttp.web.json_response({"error": "Invalid JSON"}, status=400)

        self.Pipeline.inject(data, self)
        return aiohttp.web.json_response({"status": "received"})

    async def main(self):
        self.Runner = aiohttp.web.AppRunner(self.WebChat.app)
        await self.Runner.setup()

        self.Site = aiohttp.web.TCPSite(self.Runner, "0.0.0.0", 8080)
        await self.Site.start()

        await self.stopped()  # keep the server running until shutdown

    async def stop(self):
        if hasattr(self, 'Site'):
            await self.Site.stop()
        if hasattr(self, 'Runner'):
            await self.Runner.cleanup()
        await super().stop()
