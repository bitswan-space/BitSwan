from aiohttp.web import Request

from bspump.http.web.components.base_field import BaseField
from bspump.http.web.server import env


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
            "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500",
        )
        if self.readonly:
            self.default_classes = kwargs.get(
                "default_css_classes",
                "bg-gray-500 border border-gray-300 text-white text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500",
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

    def get_params(self, default="") -> dict:
        return {self.name: {"type": str(type(self)), "description": self.description}}