import base64
from io import BytesIO

from aiohttp.web import Request

from bspump.http.web.components.field import Field
from bspump.http.web.template_env import env


class FileField(Field):
    """
    The value ends up being the bytes of the uploaded file.
    """

    def inner_html(self, default="", readonly=False):
        template = env.get_template("file-field.html")
        return template.render(
            default_input_props=self.default_input_props,
            default_classes=self.default_classes,
        )

    def clean(self, data, request: Request | None = None):
        if request.content_type == "application/json":
            decoded_data = base64.b64decode(data.get(self.name, ""))
            data[self.name] = BytesIO(decoded_data)
        else:
            # in case of not submitting any file
            if data[self.name] == b"":
                data[self.name] = BytesIO(b"")
            else:
                data[self.name] = data[self.name].file
