from aiohttp.web import Request
from bspump.http.web.components.field import Field
from bspump.http.web.template_env import env


class DateField(Field):
    """
    Renders an HTML5 <input type="date"> and
    cleans the incoming string into the same format.
    """

    def inner_html(self, default="", readonly=False):
        # default should be an ISO date string "YYYY-MM-DD"
        template = env.get_template("date-field.html")
        return template.render(
            default=default,
            default_classes=self.default_classes,
            default_input_props=self.default_input_props,
            readonly=readonly,
        )

    def clean(self, data, request: Request | None = None):
        # leave as string; browser enforces format
        value = data.get(self.name)
        if value is not None:
            # optionally, you could validate format here
            data[self.name] = value
