from aiohttp.web import Request
import json

from bspump.http.web.components.field import Field
from bspump.http.web.template_env import env


class RawJSONField(Field):
    def inner_html(self, default="", readonly=False):
        template = env.get_template("raw-json_field.html")
        return template.render(
            default=default,
            default_input_props=self.default_input_props,
            default_classes=self.default_classes,
        )

    def clean(self, data, request: Request | None = None):
        if type(data.get(self.name)) == str:
            data[self.name] = json.loads(data.get(self.name, "{}"))
