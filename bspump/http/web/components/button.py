from bspump.http.web.components import Field
from bspump.http.web.template_env import env


class Button(Field):
    def __init__(self, name, id, action, **kwargs):
        super().__init__(name, **kwargs)
        self.name = name
        self.action = action
        self.button_id = id
        self.default_classes = kwargs.get("default_css_classes", "bg-cyan-600 hover:bg-cyan-900 text-slate-100 font-bold py-2 px-4 rounded-lg mt-10"
)

    def inner_html(self, default="", readonly=False):
        template = env.get_template("button.html")
        return template.render(
            name=self.name,
            default_classes=self.default_classes,
            action=self.action,
            button_id=self.button_id
        )