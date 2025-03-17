from aiohttp.web import Request

from bspump.http.web.components.base_field import BaseField
from bspump.http.web.template_env import env


class Field(BaseField):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        if "___" in name:
            raise ValueError("Field name cannot contain '___'")
        su = super()
        su.__init__(name, **kwargs)
        self.readonly: bool = kwargs.get("readonly", False)
        self.default = kwargs.get("default", "")
        self.field_name: str = f"f___{self.name}"
        self.default_classes = kwargs.get(
            "default_css_classes",
            "bg-slate-50 autofill:shadow-[inset_0_0_0px_1000px_theme(colors.slate.50)] autofill:bg-slate-50 border-2 border-slate-200 text-gray-900 text-md rounded-lg shadow-lg shadow-slate-100 focus:outline-none focus:ring-slate-400 focus:border-slate-400 focus:bg-slate-50 block w-full p-2.5 transition-shadow duration-200 ease-in-out autofill:bg-slate-50",
        )
        if self.readonly:
            self.default_classes = kwargs.get(
                "default_css_classes",
                "bg-slate-100 border-2 border-slate-200 text-gray-900 text-md rounded-lg shadow-lg shadow-slate-100 focus:outline-none focus:ring-none block w-full p-2.5",
            )

    @property
    def default_input_props(self):
        if self.readonly:
            readonly = "readonly"
        else:
            readonly = ""

        if self.required:
            required = 'required aria-required="true"'
        else:
            required = ""
        return f'name="{self.field_name}" id="{self.field_name}" {readonly} {required}'

    def restructure_data(self, dfrom, dto):
        dto[self.name] = dfrom.get(self.field_name, self.default)

    def clean(self, data, request: Request | None = None):
        pass

    def html(self, default=""):
        if not default:
            default = self.default

        template = env.get_template("field.html")
        return template.render(
            field_name=self.field_name,
            display=self.display,
            default_classes=self.default_classes,
            hidden=self.hidden,
            inner_html=self.inner_html(default, self.readonly),
        )

    def get_params(self) -> dict:
        return {"type": type(self).__name__, "description": self.description}
