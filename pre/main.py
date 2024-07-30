import json
import os
from bspump.jupyter import *

config = None
__bitswan_dev = False


notebook_path = os.environ.get("JUPYTER_NOTEBOOK", "pipelines/main.ipynb")
if os.path.exists(notebook_path):
  with open(notebook_path) as nb:
      notebook = json.load(nb)
      for cell in notebook["cells"]:
          if cell["cell_type"] == "code":
              source = cell["source"]
              if len(source) > 0 and "#ignore" not in source[0]:
                  code = "\n".join(cell["source"])
                  exec(code)
else:
    print(f"Notebook {notebook_path} not found")
                  

App().run()
