"""
WebChat UI Components Module

This module provides the core UI components and form field classes for the WebChat system.
It includes form field implementations, template management, and HTML generation
for creating interactive chat interfaces with various input types.

Key Components:
- PromptFormBaseField: Base class for all form fields
- Various field types (TextField, IntField, FileField, etc.)
- WebChatTemplateEnv: Template environment management
- WebChatPromptForm: Form rendering and management
- WebChatResponse: Response message rendering
- WebChatWelcomeWindow: Welcome message display
"""

import base64
import json
import time
from io import BytesIO
from urllib.request import Request

import aiohttp_jinja2
import jinja2
import os
import aiohttp.web

from jinja2 import Environment

# Global aiohttp application instance for template setup
app = aiohttp.web.Application()


class PromptFormBaseField:
    """
    Base class for all form field types in the WebChat system.
    
    Provides common functionality and interface that all form fields must implement.
    This includes field properties, validation, HTML generation, and data processing.
    """
    
    def __init__(self, name, **kwargs):
        """
        Initialize a form field with common properties.
        
        Args:
            name: Field identifier name
            **kwargs: Additional field properties including:
                - hidden: Whether field should be hidden from user
                - required: Whether field is required for form submission
                - display: Human-readable display name
                - description: Field description/help text
                - default: Default value for the field
        """
        self.name = name
        self.hidden: bool = kwargs.get("hidden", False)
        self.required: bool = kwargs.get("required", False if self.hidden else True)
        self.display: str = kwargs.get("display", self.name)
        self.description: str = kwargs.get("description", "")
        self.default = kwargs.get("default", "")

    def html(self, defaults) -> str:
        """Generate HTML representation of the field (to be implemented by subclasses)."""
        pass

    def get_params(self) -> dict:
        """Get field parameters for serialization (to be implemented by subclasses)."""
        pass

    def restructure_data(self, dfrom, dto):
        """Restructure data from form submission format to internal format."""
        pass

    def clean(self, data, request: Request = None):
        """Clean and validate field data (to be implemented by subclasses)."""
        pass


class PromptFormField(PromptFormBaseField):
    """
    Standard form field implementation with common HTML input functionality.
    
    Provides a complete implementation of form field behavior including
    HTML generation, data processing, and validation.
    """
    
    def __init__(self, name, **kwargs):
        """
        Initialize a standard form field.
        
        Args:
            name: Field identifier name
            **kwargs: Additional field properties including:
                - readonly: Whether field is read-only
                - default_css_classes: CSS classes for styling
        """
        super().__init__(name, **kwargs)
        
        # Validate field name (no double underscores allowed)
        if "___" in name:
            raise ValueError("Field name cannot contain '___'")
            
        # Call parent constructor again to ensure proper initialization
        su = super()
        su.__init__(name, **kwargs)
        
        self.readonly: bool = kwargs.get("readonly", False)
        self.default = kwargs.get("default", "")
        self.field_name: str = f"{self.name}"
        
        # Set default CSS classes based on field state
        self.default_classes = kwargs.get(
            "default_css_classes",
            "text-primary border border-secondary text-sm px-4 py-1 rounded-md font-mono w-full max-w-[150px] mx-2",
        )
        
        # Apply disabled styling for readonly fields
        if self.readonly:
            self.default_classes = kwargs.get(
                "default_css_classes",
                "text-primary border border-secondary text-sm px-4 py-1 rounded-md font-mono w-full max-w-[150px] mx-2 opacity-50 cursor-not-allowed",
            )

    @property
    def default_input_props(self):
        """
        Generate HTML input attributes based on field properties.
        
        Returns:
            str: HTML attributes string for the input element
        """
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
        """
        Extract field value from form data and store in destination dictionary.
        
        Args:
            dfrom: Source dictionary (form submission data)
            dto: Destination dictionary (processed data)
        """
        dto[self.name] = dfrom.get(self.field_name, self.default)

    def clean(self, data, request: Request | None = None):
        """Clean field data (base implementation does nothing)."""
        pass

    def get_html(self, template_env, default=""):
        """
        Generate HTML representation of the field using Jinja2 templates.
        
        Args:
            template_env: Jinja2 template environment
            default: Default value to display
            
        Returns:
            str: Rendered HTML for the field
        """
        if not default:
            default = self.default

        template = template_env.get_template("components/field.html")
        return template.render(
            field_name=self.field_name,
            display=self.display,
            default_classes=self.default_classes,
            hidden=self.hidden,
            inner_html=self.inner_html(
                template_env, default, self.readonly, self.field_name
            ),
        )

    def get_params(self) -> dict:
        """
        Get field parameters for serialization.
        
        Returns:
            dict: Field parameters including type and description
        """
        return {"type": type(self).__name__, "description": self.description}


class CheckboxField(PromptFormField):
    """
    Checkbox form field for boolean values.
    
    Handles checkbox input with proper boolean conversion and validation.
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize checkbox field with boolean default value."""
        super().__init__(*args, **kwargs)
        self.default = self.default or False

    def inner_html(
        self, template_env=None, default="", readonly=False, field_name=None
    ):
        """
        Generate inner HTML for checkbox input.
        
        Args:
            template_env: Jinja2 template environment
            default: Default checkbox state
            readonly: Whether field is read-only
            field_name: Field identifier
            
        Returns:
            str: Rendered HTML for checkbox input
        """
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
        """
        Clean checkbox data by converting string values to boolean.
        
        Args:
            data: Dictionary containing field data
            request: HTTP request object (unused)
        """
        if type(data.get(self.name)) == str:
            data[self.name] = data.get(self.name, False) == "on"


class ChoiceField(PromptFormField):
    """
    Dropdown choice field for selecting from predefined options.
    
    Renders as a select element with provided choice options.
    """
    
    def __init__(self, name, choices, **kwargs):
        """
        Initialize choice field with available options.
        
        Args:
            name: Field identifier name
            choices: List of available choice options
            **kwargs: Additional field properties
        """
        super().__init__(name, **kwargs)
        self.choices = choices

    def inner_html(
        self, template_env=None, default="", readonly=False, field_name=None
    ):
        """
        Generate inner HTML for choice dropdown.
        
        Args:
            template_env: Jinja2 template environment
            default: Default selected value
            readonly: Whether field is read-only
            field_name: Field identifier
            
        Returns:
            str: Rendered HTML for choice dropdown
        """
        template = template_env.get_template("components/choice-field.html")
        return template.render(
            default=default,
            choices=self.choices,
            default_classes=self.default_classes,
            default_input_props=self.default_input_props,
        )


class FileField(PromptFormField):
    """
    File upload field for handling file uploads.
    
    The value ends up being the bytes of the uploaded file.
    Supports both multipart form data and base64-encoded JSON submissions.
    """

    def inner_html(
        self, template_env=None, default="", readonly=False, field_name=None
    ):
        """
        Generate inner HTML for file input.
        
        Args:
            template_env: Jinja2 template environment
            default: Default value (unused for file fields)
            readonly: Whether field is read-only
            field_name: Field identifier
            
        Returns:
            str: Rendered HTML for file input
        """
        template = template_env.get_template("components/input-field.html")
        return template.render(
            default_input_props=self.default_input_props,
            default_classes=self.default_classes,
            field_name=field_name,
            field_type="file",
        )

    def clean(self, data, request: Request | None = None):
        """
        Process file upload data and convert to BytesIO object.
        
        Handles both multipart form data and base64-encoded JSON submissions.
        
        Args:
            data: Dictionary containing field data
            request: HTTP request object for content type detection
        """
        if request.content_type == "application/json":
            # Handle base64-encoded file data from JSON submissions
            decoded_data = base64.b64decode(data.get(self.name, ""))
            data[self.name] = BytesIO(decoded_data)
        else:
            # Handle multipart form data
            # in case of not submitting any file
            if data[self.name] == b"":
                data[self.name] = BytesIO(b"")
            else:
                data[self.name] = data[self.name].file


class FloatField(PromptFormField):
    """
    Numeric input field for floating-point values.
    
    Renders as a number input with proper validation and type conversion.
    """
    
    def inner_html(self, template_env=None, default=0, readonly=False, field_name=None):
        """
        Generate inner HTML for float number input.
        
        Args:
            template_env: Jinja2 template environment
            default: Default numeric value
            readonly: Whether field is read-only
            field_name: Field identifier
            
        Returns:
            str: Rendered HTML for number input
        """
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
        """
        Clean float data by converting string values to float.
        
        Args:
            data: Dictionary containing field data
            request: HTTP request object (unused)
        """
        if type(data.get(self.name)) == str:
            data[self.name] = float(data.get(self.name, 0))


class IntField(PromptFormField):
    """
    Numeric input field for integer values.
    
    Renders as a number input with proper validation and type conversion.
    """
    
    def inner_html(self, template_env=None, default=0, readonly=False, field_name=None):
        """
        Generate inner HTML for integer number input.
        
        Args:
            template_env: Jinja2 template environment
            default: Default numeric value
            readonly: Whether field is read-only
            field_name: Field identifier
            
        Returns:
            str: Rendered HTML for number input
        """
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
        """
        Clean integer data by converting string values to int.
        
        Args:
            data: Dictionary containing field data
            request: HTTP request object (unused)
        """
        if type(data.get(self.name)) == str:
            data[self.name] = int(data.get(self.name, 0))


class TextField(PromptFormField):
    """
    Standard text input field for string values.
    
    Renders as a text input with standard text field behavior.
    """
    
    def inner_html(
        self, template_env=None, default="", readonly=False, field_name=None
    ):
        """
        Generate inner HTML for text input.
        
        Args:
            template_env: Jinja2 template environment
            default: Default text value
            readonly: Whether field is read-only
            field_name: Field identifier
            
        Returns:
            str: Rendered HTML for text input
        """
        template = template_env.get_template("components/input-field.html")
        return template.render(
            default=default,
            default_classes=self.default_classes,
            default_input_props=self.default_input_props,
            field_name=field_name,
            field_type="text",
        )


class DateField(PromptFormField):
    """
    Date input field for date selection.
    
    Renders as a date input with browser-native date picker support.
    """
    
    def inner_html(
        self, template_env=None, default="", readonly=False, field_name=None
    ):
        """
        Generate inner HTML for date input.
        
        Args:
            template_env: Jinja2 template environment
            default: Default date value
            readonly: Whether field is read-only
            field_name: Field identifier
            
        Returns:
            str: Rendered HTML for date input
        """
        template = template_env.get_template("components/input-field.html")
        return template.render(
            default=default,
            default_classes=self.default_classes,
            default_input_props=self.default_input_props,
            field_name=field_name,
            field_type="date",
        )


class RawJSONField(PromptFormField):
    """
    JSON input field for complex data structures.
    
    Accepts JSON string input and parses it into Python objects.
    Useful for structured data input and configuration.
    """
    
    def inner_html(self, template_env=None, default="", readonly=False):
        """
        Generate inner HTML for JSON textarea input.
        
        Args:
            template_env: Jinja2 template environment
            default: Default JSON value
            readonly: Whether field is read-only
            
        Returns:
            str: Rendered HTML for JSON textarea
        """
        template = template_env.get_template("components/raw-json_field.html")
        return template.render(
            default=default,
            default_input_props=self.default_input_props,
            default_classes=self.default_classes,
        )

    def clean(self, data, request: Request | None = None):
        """
        Clean JSON data by parsing string values into Python objects.
        
        Args:
            data: Dictionary containing field data
            request: HTTP request object (unused)
        """
        if type(data.get(self.name)) == str:
            data[self.name] = json.loads(data.get(self.name, "{}"))


class WebChatTemplateEnv:
    """
    Template environment manager for WebChat components.
    
    Handles Jinja2 template setup, directory management, and template loading.
    Supports both built-in templates and custom template directories.
    """
    
    def __init__(self, extra_template_dir: str = None):
        """
        Initialize template environment with optional custom template directory.
        
        Args:
            extra_template_dir: Optional path to additional template directory
        """
        self.extra_template_dir = extra_template_dir
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.template_env = self.create_template_env()

    def create_template_env(self) -> Environment:
        """
        Create and configure Jinja2 template environment.
        
        Sets up template loaders, autoescaping, and other Jinja2 settings.
        
        Returns:
            Environment: Configured Jinja2 template environment
            
        Raises:
            ValueError: If template directory doesn't exist
        """
        main_template_dir = os.path.join(self.base_dir, "templates")
        loader_paths = []

        # Validate main template directory exists
        if not os.path.isdir(main_template_dir):
            raise ValueError(f"Template directory '{main_template_dir}' does not exist")
        loader_paths.append(main_template_dir)

        # Add custom template directory if provided
        if self.extra_template_dir:
            loader_paths.append(self.extra_template_dir)

        # Setup aiohttp-jinja2 integration
        aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(loader_paths))

        # Create Jinja2 environment with proper configuration
        template_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(loader_paths),
            autoescape=jinja2.select_autoescape(["html", "xml"]),
        )

        return template_env

    def get_jinja_env(self) -> Environment:
        """
        Get the configured Jinja2 template environment.
        
        Returns:
            Environment: Configured Jinja2 template environment
        """
        return self.template_env


class WebChatPromptForm:
    """
    Form container for displaying interactive prompts to users.
    
    Manages form field rendering, submission handling, and HTML generation
    for user input forms in the chat interface.
    """
    
    def __init__(self, fields: [PromptFormBaseField], awaiting_text: str = None):
        """
        Initialize prompt form with fields and optional awaiting message.
        
        Args:
            fields: List of form fields to display
            awaiting_text: Optional text to show while waiting for user input
        """
        self.fields = fields
        self.awaiting_text = awaiting_text

    def get_context(self, template_env: Environment) -> dict:
        """
        Prepare template context for form rendering.
        
        Args:
            template_env: Jinja2 template environment
            
        Returns:
            dict: Template context with form inputs and metadata
        """
        rendered_inputs = [field.get_html(template_env) for field in self.fields]
        context = {
            "form_inputs": rendered_inputs,
            "awaiting_text": self.awaiting_text,
            "form_id": f"prompt-form-{int(time.time() * 1000)}",  # Unique form ID
        }
        return context

    def get_html(self, template_env: Environment) -> str:
        """
        Generate complete HTML for the prompt form.
        
        Args:
            template_env: Jinja2 template environment
            
        Returns:
            str: Rendered HTML for the complete form
        """
        template = template_env.get_template("components/prompt-form.html")
        return template.render(self.get_context(template_env))


class WebChatWelcomeWindow:
    """
    Welcome message display component for chat sessions.
    
    Provides a customizable welcome message that can be displayed
    at the beginning of chat sessions or as informational content.
    """
    
    def __init__(self, welcome_text: str, is_html: bool = False):
        """
        Initialize welcome window with message content.
        
        Args:
            welcome_text: Welcome message text or HTML content
            is_html: Whether the content should be treated as HTML
        """
        self.welcome_text = welcome_text or ""
        self.is_html = is_html

    def get_context(self) -> dict:
        """
        Prepare template context for welcome message rendering.
        
        Returns:
            dict: Template context with welcome message data
        """
        context = {
            "welcome_text": self.welcome_text,
            "is_html": self.is_html,
        }
        return context

    def get_html(self, template_env: Environment) -> str:
        """
        Generate HTML for the welcome message window.
        
        Args:
            template_env: Jinja2 template environment
            
        Returns:
            str: Rendered HTML for the welcome message
        """
        template = template_env.get_template("components/welcome-message-box.html")
        return template.render(self.get_context())


class WebChatResponse:
    """
    Response message component for chat interactions.
    
    Handles rendering of both user responses and system messages
    in the chat interface with proper styling and formatting.
    """
    
    def __init__(
        self, input_html: str, user_response: bool = False, is_html: bool = False
    ):
        """
        Initialize response message with content and type.
        
        Args:
            input_html: Response content (text or HTML)
            user_response: Whether this is a user response (affects styling)
            is_html: Whether the content should be treated as HTML
        """
        self.input_html = input_html or ""
        self.user_response = user_response
        self.is_html = is_html

    def get_context(self) -> dict:
        """
        Prepare template context for response rendering.
        
        Returns:
            dict: Template context with response data
        """
        return {
            "response_text": self.input_html,
            "is_html": self.is_html,
        }

    def get_html(self, template_env: Environment) -> str:
        """
        Generate HTML for the response message.
        
        Uses different templates for user responses vs system messages
        to provide appropriate styling and layout.
        
        Args:
            template_env: Jinja2 template environment
            
        Returns:
            str: Rendered HTML for the response message
        """
        if self.user_response:
            template = template_env.get_template("components/user-response.html")
        else:
            template = template_env.get_template("components/web-chat-response.html")
        return template.render(self.get_context())
