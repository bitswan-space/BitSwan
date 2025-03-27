import os

from bspump.http_webchat.server.app import create_template_env

base_dir = os.path.dirname(os.path.abspath(__file__))
api_dir = os.path.abspath(os.path.join(base_dir, 'templates'))
if not os.path.isdir(api_dir):
    raise ValueError(f"Template directory '{api_dir}' does not exist")

template_env = create_template_env(api_dir)

'''
print("Available templates:")
for template_name in template_env.list_templates():
    print(template_name)
'''