import json
import os
from bspump.jupyter import *
import bspump.jupyter
import ast

config = None
__bitswan_dev = False

notebook_path = os.environ.get("JUPYTER_NOTEBOOK", "pipelines/main.ipynb")

def exec_cell(cell, cell_number, ctx):
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
                if bspump.jupyter.bitswan_auto_pipeline.get("sink") is not None:
                    clean_code = """
# load locals from __bs_step_locals
for key, value in __bs_step_locals.items():
    locals()[key] = value
""" + clean_code + """
__bs_step_locals = locals()
                    """

                    parsed_code = ast.parse(clean_code)

                    # Step 3: Create a new function definition
                    new_function = ast.FunctionDef(
                        name=f"step_{cell_number}",
                        args=ast.arguments(
                            posonlyargs=[], args=[ast.arg(arg="event", annotation=None)], kwonlyargs=[], kw_defaults=[], defaults=[]
                        ),
                        body=parsed_code.body,
                        decorator_list=[ast.Name(id="step", ctx=ast.Load())],
                    )

                    # Step 4: Wrap the function definition in a module
                    module = ast.Module(body=[new_function], type_ignores=[])

                    # Step 5: Compile the module
                    module = ast.fix_missing_locations(module)
                    compiled_code = compile(module, filename="<ast>", mode="exec")
                    # exec the code
                    exec(compiled_code, ctx)
                else:
                    exec(clean_code, ctx)
            except Exception as e:
                print(f"Error in cell: {cell_number}\n{clean_code}")
                # print traceback
                import traceback
                traceback.print_exc()

if bspump.jupyter.bitswan_auto_pipeline.get("sink") is not None:
    register_sink(bspump.jupyter.bitswan_auto_pipeline.get("sink"))

if os.path.exists(notebook_path):
  with open(notebook_path) as nb:
      notebook = json.load(nb)
      cell_number = 0
      for cell in notebook["cells"]:
          cell_number += 1
          exec_cell(cell, cell_number, globals())
else:
    print(f"Notebook {notebook_path} not found")
                  
App().run()
