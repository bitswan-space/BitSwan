from aiohttp.web import Request
from bspump.http.web.components import BaseField
from bspump.http.web.template_env import env
import json


class TableComponent(BaseField):
    """
    A component that displays data in a table format with configurable columns.
    Supports adding new rows with editable fields and various input types.

    Supported input_type values:
    - "text": Text input for general text
    - "email": Email input with format validation
    - "number": Number input for numeric values
    - "date": Date picker for date selection
    - "datetime": DateTime picker for date and time selection
    - "url": URL input for website links
    - "textarea": Multi-line text area
    - "select": Dropdown selection (requires choices list)
    - "checkbox": Boolean checkbox input

    Example of defining columns:
    cols = [
        {"key": "email", "display": "Email Address", "input_type": "email", "required": True},
        {"key": "first_name", "display": "First Name", "input_type": "text", "required": False},
        {"key": "last_name", "display": "Last Name", "input_type": "text", "required": False},
        {"key": "phone", "display": "Phone Number", "input_type": "text", "required": True},
        {"key": "notes", "display": "Notes", "input_type": "textarea", "required": False},
        {"key": "status", "display": "Status", "input_type": "select", "choices": ["Active", "Inactive", "Pending", "Suspended"], "required": True},
    ]
    """

    def __init__(
        self, name, data_provider=None, columns=None, editable=False, **kwargs
    ):
        super().__init__(name, **kwargs)
        self.field_name = f"f___{self.name}"
        self.data_provider = data_provider
        self.columns = columns or []
        self.editable = editable

    def html(self, default=""):
        data = []
        if self.data_provider:
            try:
                data = self.data_provider()
            except Exception as e:
                data = [{"error": f"Failed to load data: {str(e)}"}]

        template = env.get_template("table.html")
        return template.render(
            name=self.name,
            field_name=self.field_name,
            display=self.display,
            columns=self.columns,
            data=data,
            hidden=self.hidden,
            editable=self.editable,
            default=default,
        )

    def restructure_data(self, dfrom, dto):
        table_data = dfrom.get(self.field_name, "[]")
        try:
            dto[self.name] = json.loads(table_data)
        except (json.JSONDecodeError, TypeError):
            dto[self.name] = []

    def clean(self, data, request: Request = None):
        pass
