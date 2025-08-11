from aiohttp.web import Request
from bspump.http.web.components.field import Field
from bspump.http.web.template_env import env


class DateTimeField(Field):
    """
    Renders an HTML5 <input type="datetime-local"> and
    cleans the incoming string into the same ISO format.
    """

    def inner_html(self, default="", readonly=False):
        # default should be "YYYY-MM-DDTHH:MM"
        template = env.get_template("datetime-field.html")
        return template.render(
            default=default,
            default_classes=self.default_classes,
            default_input_props=self.default_input_props,
            readonly=readonly,
        )

    def clean(self, data, request: Request | None = None):
        value = data.get(self.name)
        if value is not None:
            # browser provides "YYYY-MM-DDTHH:MM"; keep as-is or convert
            data[self.name] = value
