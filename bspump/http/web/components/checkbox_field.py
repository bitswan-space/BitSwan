from aiohttp.web import Request

from bspump.http.web.components.field import Field
from bspump.http.web.template_env import env


class CheckboxField(Field):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default = self.default or False

    def inner_html(self, default="", readonly=False):
        readonly_attr = "disabled" if readonly else ""

        template = env.get_template("checkbox-field.html")
        return template.render(
            default=default,
            readonly=readonly,
            default_classes=self.default_classes,
            default_input_props=self.default_input_props,
            readonly_attr=readonly_attr,
        )

    def clean(self, data, request: Request | None = None):
        if type(data.get(self.name)) == str:
            data[self.name] = data.get(self.name, False) == "on"
