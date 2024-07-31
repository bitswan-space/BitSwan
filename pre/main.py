import json
import os
from bspump.jupyter import *

config = None
__bitswan_dev = False

notebook_path = os.environ.get("JUPYTER_NOTEBOOK", "pipelines/main.ipynb")
if os.path.exists(notebook_path):
  with open(notebook_path) as nb:
      notebook = json.load(nb)
      cell_number = 0
      for cell in notebook["cells"]:
          cell_number += 1
          if cell["cell_type"] == "code":
              source = cell["source"]
              if len(source) > 0 and "#ignore" not in source[0]:
                  code = "\n".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]
                  clean_code = ""
                  for line in code.split("\n"):
                      if line.startswith("!"):
                          continue
                      clean_code += line + "\n"
                  try:
                      exec(clean_code)
                  except Exception as e:
                      print(f"Error in cell: {cell_number}\n{clean_code}")
                      # print traceback
                      import traceback
                      traceback.print_exc()
else:
    print(f"Notebook {notebook_path} not found")
                  
App().run()
