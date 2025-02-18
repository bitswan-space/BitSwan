from bspump.http.web.components.field import Field
from bspump.http.web.template_env import env


class ChoiceField(Field):
    def __init__(self, name, choices, **kwargs):
        super().__init__(name, **kwargs)
        self.choices = choices

    def inner_html(self, default="", readonly=False):
        template = env.get_template("choice-field.html")
        return template.render(
            default=default,
            choices=self.choices,
            default_classes=self.default_classes,
            default_input_props=self.default_input_props,
        )
