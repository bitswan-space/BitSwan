from .base_field import BaseField
from .field import Field
from .float_field import FloatField
from .int_field import IntField
from .checkbox_field import CheckboxField
from .text_field import TextField
from .choice_field import ChoiceField
from .field_set import FieldSet
from .file_field import FileField
from .raw_json import RawJSONField
from .button import Button
from .date_field import DateField
from .datetime_field import DateTimeField

FIELD_REGISTRY = {
    "BaseField": BaseField,
    "Field": Field,
    "FloatField": FloatField,
    "IntField": IntField,
    "CheckboxField": CheckboxField,
    "TextField": TextField,
    "ChoiceField": ChoiceField,
    "FieldSet": FieldSet,
    "FileField": FileField,
    "RawJSONField": RawJSONField,
    "Button": Button,
    "DateField": DateField,
    "DateTimeField": DateTimeField,
    # "EditableTableComponent": EditableTableComponent not included to avoid circular imports
}

def get_field_class(field_type):
    """
    Returns the field class associated with the given field type.
    
    :param field_type: The type of the field as a string.
    :return: The corresponding field class, defaults to TextField if not found.
    """
    return FIELD_REGISTRY.get(field_type, TextField)

def get_all_field_classes():
    """
    Returns a list of all field classes registered in the FIELD_REGISTRY.
    
    :return: A list of all field classes.
    """
    return list(FIELD_REGISTRY.values())