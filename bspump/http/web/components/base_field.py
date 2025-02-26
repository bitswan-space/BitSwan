from aiohttp.web import Request


class BaseField:
    def __init__(self, name, **kwargs):
        self.name = name
        self.hidden: bool = kwargs.get("hidden", False)
        self.required: bool | None = kwargs.get("required", True)
        self.display: str = kwargs.get("display", self.name)
        self.description: str = kwargs.get("description", "")
        self.default = kwargs.get("default", "")

        if self.required is None:
            self.required = not self.hidden
        else:
            self.required = True

    def html(self, defaults) -> str:
        pass

    def get_params(self, defaults) -> dict:
        pass

    def restructure_data(self, dfrom, dto):
        pass

    def clean(self, data, request: Request = None):
        pass
