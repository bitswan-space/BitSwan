from jinja2 import Environment, FileSystemLoader
import importlib.util
from pathlib import Path
import os


def find_module_path(module_name):
    spec = importlib.util.find_spec(module_name)
    if spec and spec.origin:
        return spec.origin
    else:
        return f"Module '{module_name}' not found or built-in."


path = str(
    Path(os.path.split(find_module_path("bspump"))[:-1][0])
    / "http"
    / "web"
    / "templates"
)
env = Environment(loader=FileSystemLoader(path))
