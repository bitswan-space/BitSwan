import base64
import json
import time
from io import BytesIO
from typing import List
from urllib.request import Request

import aiohttp_jinja2
import jinja2
import os
import aiohttp.web

from jinja2 import Environment

app = aiohttp.web.Application()

class PromptFormBaseField:
    def __init__(self, name, **kwargs):
        self.name = name
        self.hidden: bool = kwargs.get("hidden", False)
        self.required: bool = kwargs.get("required", False if self.hidden else True)
        self.display: str = kwargs.get("display", self.name)
        self.description: str = kwargs.get("description", "")
        self.default = kwargs.get("default", "")

    def html(self, defaults) -> str:
        pass

    def get_params(self) -> dict:
        pass

    def restructure_data(self, dfrom, dto):
        pass

    def clean(self, data, request: Request = None):
        pass


class PromptFormField(PromptFormBaseField):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        if "___" in name:
            raise ValueError("Field name cannot contain '___'")
        su = super()
        su.__init__(name, **kwargs)
        self.readonly: bool = kwargs.get("readonly", False)
        self.default = kwargs.get("default", "")
        self.field_name: str = f"{self.name}"
        self.default_classes = kwargs.get(
            "default_css_classes",
            "text-primary border border-secondary text-sm px-4 py-1 rounded-md font-mono w-full max-w-[150px] mx-2",
        )
        if self.readonly:
            self.default_classes = kwargs.get(
                "default_css_classes",
                "text-primary border border-secondary text-sm px-4 py-1 rounded-md font-mono w-full max-w-[150px] mx-2 opacity-50 cursor-not-allowed",
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

    def get_html(self, template_env, default=""):
        if not default:
            default = self.default

        template = template_env.get_template("components/field.html")
        return template.render(
            field_name=self.field_name,
            display=self.display,
            default_classes=self.default_classes,
            hidden=self.hidden,
            inner_html=self.inner_html(template_env, default, self.readonly, self.field_name),
        )

    def get_params(self) -> dict:
        return {"type": type(self).__name__, "description": self.description}


class CheckboxField(PromptFormField):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default = self.default or False

    def inner_html(self, template_env=None, default="", readonly=False, field_name=None):
        readonly_attr = "disabled" if readonly else ""

        template = template_env.get_template("components/input-field.html")
        return template.render(
            default=default,
            readonly=readonly,
            default_classes=self.default_classes,
            default_input_props=self.default_input_props,
            readonly_attr=readonly_attr,
            field_name=field_name,
            field_type="checkbox",
        )

    def clean(self, data, request: Request | None = None):
        if type(data.get(self.name)) == str:
            data[self.name] = data.get(self.name, False) == "on"

class ChoiceField(PromptFormField):
    def __init__(self, name, choices, **kwargs):
        super().__init__(name, **kwargs)
        self.choices = choices

    def inner_html(self, template_env=None, default="", readonly=False, field_name=None):
        template = template_env.get_template("components/choice-field.html")
        return template.render(
            default=default,
            choices=self.choices,
            default_classes=self.default_classes,
            default_input_props=self.default_input_props,
        )

class FileField(PromptFormField):
    """
    The value ends up being the bytes of the uploaded file.
    """

    def inner_html(self, template_env=None, default="", readonly=False, field_name=None):
        template = template_env.get_template("components/input-field.html")
        return template.render(
            default_input_props=self.default_input_props,
            default_classes=self.default_classes,
            field_name=field_name,
            field_type="file",
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

class FloatField(PromptFormField):
    def inner_html(self, template_env=None, default=0, readonly=False, field_name=None):
        if not default:
            default = 0.0

        template = template_env.get_template("components/input-field.html")
        return template.render(
            default=default,
            default_input_props=self.default_input_props,
            default_classes=self.default_classes,
            field_name=field_name,
            field_type="number",
        )

    def clean(self, data, request: Request | None = None):
        if type(data.get(self.name)) == str:
            data[self.name] = float(data.get(self.name, 0))

class IntField(PromptFormField):
    def inner_html(self, template_env=None, default=0, readonly=False, field_name=None):
        if not default:
            default = 0

        template = template_env.get_template("components/input-field.html")
        return template.render(
            default=default,
            default_input_props=self.default_input_props,
            default_classes=self.default_classes,
            field_name=field_name,
            field_type="number",
        )

    def clean(self, data, request: Request | None = None):
        if type(data.get(self.name)) == str:
            data[self.name] = int(data.get(self.name, 0))

class TextField(PromptFormField):
    def inner_html(self, template_env=None, default="", readonly=False, field_name=None):
        template = template_env.get_template("components/input-field.html")
        return template.render(
            default=default,
            default_classes=self.default_classes,
            default_input_props=self.default_input_props,
            field_name=field_name,
            field_type="text",
        )

class DateField(PromptFormField):
    def inner_html(self, template_env=None, default="", readonly=False, field_name=None):
        template = template_env.get_template("components/input-field.html")
        return template.render(
            default=default,
            default_classes=self.default_classes,
            default_input_props=self.default_input_props,
            field_name=field_name,
            field_type="date",
        )

class RawJSONField(PromptFormField):
    def inner_html(self, template_env=None, default="", readonly=False):
        template = template_env.get_template("components/raw-json_field.html")
        return template.render(
            default=default,
            default_input_props=self.default_input_props,
            default_classes=self.default_classes,
        )

    def clean(self, data, request: Request | None = None):
        if type(data.get(self.name)) == str:
            data[self.name] = json.loads(data.get(self.name, "{}"))

class WebChatTemplateEnv:
    def __init__(self, extra_template_dir: str = None):
        """
        Creates template environment on user side that will be then used for creating other components
        :param extra_template_dir: path to template directory, could be none, because user can specify the templates as strings
        """
        self.extra_template_dir = extra_template_dir
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.template_env = self.create_template_env()

    def create_template_env(self) -> Environment:
        main_template_dir = os.path.join(self.base_dir, "templates")
        loader_paths = []

        if not os.path.isdir(main_template_dir):
            raise ValueError(f"Template directory '{main_template_dir}' does not exist")
        loader_paths.append(main_template_dir)

        if self.extra_template_dir:
            loader_paths.append(self.extra_template_dir)

        aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(loader_paths))

        template_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(loader_paths),
            autoescape=jinja2.select_autoescape(["html", "xml"]),
        )

        return template_env

    def get_jinja_env(self) -> Environment:
        """
        :return: Environment variable
        """
        return self.template_env

class WebChatPromptForm:
    def __init__(self, fields: [PromptFormBaseField], awaiting_text: str = None):
        """
        Class for defining the form.
        :param form_inputs: list of individual input fields
        :param awaiting_text: optional awaiting message to render instead of inputs
        """
        self.fields = fields
        self.awaiting_text = awaiting_text

    def get_context(self, template_env: Environment) -> dict:
        rendered_inputs = [
            field.get_html(template_env) for field in self.fields
        ]
        context = {
            "form_inputs": rendered_inputs,
            "awaiting_text": self.awaiting_text,
            "form_id": f"prompt-form-{int(time.time() * 1000)}",
        }
        return context
    def get_html(self, template_env: Environment) -> str:
        template = template_env.get_template("components/prompt-form.html")
        return template.render(self.get_context(template_env))


class WebChatWelcomeWindow:
    def __init__(self, welcome_text: str):
        """
        Class for defining the first window that is rendered and is visible all the time
        :param welcome_text: text or html string that should be rendered
        :param prompt_form: html of the prompt that is rendered with the window
        """
        self.welcome_text = welcome_text or ""

    def get_context(self) -> dict:
        context = {
            "welcome_text": self.welcome_text,
        }
        return context

    def get_html(self, template_env: Environment) -> str:
        template = template_env.get_template("components/welcome-message-box.html")
        return template.render(self.get_context())


class WebChatResponse:
    def __init__(
        self,
        input_html: str,
        user_response: bool = False
    ):
        """
        Class for creatin one response
        :param input_html: could be just string or html string
        :param prompt_form: html of the prompt that is rendered with the window
        """
        self.input_html = input_html or ""
        self.user_response = user_response

    def get_context(self) -> dict:
        return {
            "response_text": self.input_html,
        }

    def get_html(self, template_env: Environment) -> str:
        if self.user_response:
            template = template_env.get_template("components/user-response.html")
        else:
            template = template_env.get_template("components/web-chat-response.html")
        return template.render(self.get_context())


class WebChatResponseSequence:
    def __init__(self, responses: List[WebChatResponse]):
        """
        Class that defines and renders sequence of responses
        :param responses: list of instances of class WebChatResponse
        """
        self.responses = responses

    def get_html(self, template_env: Environment) -> str:
        rendered_responses = [
            response.get_html(template_env) for response in self.responses
        ]
        js_safe_responses = json.dumps(rendered_responses)
        context = {
            "responses": js_safe_responses,
        }
        template = template_env.get_template(
            "components/web-chat-sequence-response.html"
        )
        return template.render(context)
