from bspump.http.web.components.field import Field
from bspump.http.web.template_env import env


class TextField(Field):
    def inner_html(self, default="", readonly=False):
        template = env.get_template("text-field.html")
        return template.render(
            default=default,
            default_classes=self.default_classes,
            default_input_props=self.default_input_props,
        )
