from aiohttp.web import Request

from bspump.http.web.components.field import Field
from bspump.http.web.template_env import env


class FloatField(Field):
    def inner_html(self, default=0, readonly=False):
        if not default:
            default = 0.0

        template = env.get_template("number-field.html")
        return template.render(
            default=default,
            default_input_props=self.default_input_props,
            default_classes=self.default_classes,
        )

    def clean(self, data, request: Request | None = None):
        if type(data.get(self.name)) == str:
            data[self.name] = float(data.get(self.name, 0))
