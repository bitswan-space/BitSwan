from bspump.http.web.components import BaseField
from bspump.http.web.template_env import env


class Button(BaseField):
    def __init__(self, button_id, name, on_click, **kwargs):
        super().__init__(name, **kwargs)
        self.name = name
        self.on_click = on_click
        self.button_id = button_id
        self.required: bool = kwargs.get("required", False)
        self.default_classes = kwargs.get(
            "default_css_classes",
            "bg-cyan-600 hover:bg-cyan-900 text-slate-100 font-bold py-2 px-4 rounded-lg",
        )

    def html(self, default="", readonly=False):
        template = env.get_template("button.html")
        return template.render(
            name=self.name,
            default_classes=self.default_classes,
            on_click=self.on_click,
            button_id=self.button_id,
        )
