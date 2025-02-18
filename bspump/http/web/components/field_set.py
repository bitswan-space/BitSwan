from bspump.http.web.components.base_field import BaseField
from bspump.http.web.template_env import env


class FieldSet(BaseField):
    def __init__(
        self, name, fields=None, fieldset_intro="", display="", required=True, **kwargs
    ):
        super().__init__(name, **kwargs)
        su = super()
        self.fields = fields
        if fields is None:
            self.fields = []
        su.__init__(name, required=required)
        self.display = display if display else name
        self.default = {}
        self.fieldset_intro = fieldset_intro
        self.prefix = f"fieldset___{self.name}___"

    def set_subfield_names(self):
        for field in self.fields:
            field.field_name = f"{self.prefix}{field.name}"

    def html(self, defaults={}):
        self.set_subfield_names()
        self.set_subfield_names()
        fields_html = [
            field.html(defaults.get(field.name, field.default)) for field in self.fields
        ]
        template = env.get_template("fieldset.html")
        return template.render(
            display=self.display, fieldset_intro=self.fieldset_intro, fields=fields_html
        )
