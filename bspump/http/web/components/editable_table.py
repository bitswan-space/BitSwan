from aiohttp.web import Request
from bspump.http.web.components import BaseField
from bspump.http.web.components.registry import FIELD_REGISTRY
from bspump.http.web.template_env import env


class EditableTableComponent(BaseField):
    """
    A component that allows users to dynamically define table fields
    using existing field types like TextField, IntField, etc.
    """
    
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.field_name = f"f___{self.name}"
        self.available_field_types = list(FIELD_REGISTRY.keys())
        
    def html(self, default="", readonly=False):
        template = env.get_template("editable-table.html")
        return template.render(
            name=self.name,
            field_name=self.field_name,
            display=self.display,
            available_field_types=self.available_field_types,
            hidden=self.hidden,
            readonly=readonly,
            default=default
        )
        
    def restructure_data(self, dfrom, dto):
        dto[self.name] = dfrom.get(self.field_name, [])