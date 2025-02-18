from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader("bspump/http/web/templates"))
