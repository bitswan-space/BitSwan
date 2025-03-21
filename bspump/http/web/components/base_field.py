from aiohttp.web import Request


class BaseField:
    def __init__(self, name, **kwargs):
        self.name = name
        self.hidden: bool = kwargs.get("hidden", False)
        self.required: bool = kwargs.get("required", False if self.hidden else True)
        self.display: str = kwargs.get("display", self.name)
        self.description: str = kwargs.get("description", "")
        self.default = kwargs.get("default", "")

    def html(self, defaults) -> str:
        pass

    def get_params(self) -> dict:
        pass

    def restructure_data(self, dfrom, dto):
        pass

    def clean(self, data, request: Request = None):
        pass
