import json
import os
import ast

config = None
__bitswan_dev = False
__bs_cell_code_contents: dict[int, str] = {}

from bspump.jupyter import *  # noqa: F403
import bspump.jupyter


def exec_cell(cell, cell_number, ctx):
    if cell["cell_type"] == "code":
        source = cell["source"]
        if len(source) > 0 and "#ignore" not in source[0]:
            code = (
                "\n".join(cell["source"])
                if isinstance(cell["source"], list)
                else cell["source"]
            )
            clean_code = ""
            for line in code.split("\n"):
                if line.startswith("!"):
                    continue
                clean_code += line + "\n"
            __bs_cell_code_contents[cell_number] = clean_code
            try:
                if bspump.jupyter.bitswan_auto_pipeline.get("sink") is not None:
                    clean_code = f"""
global __bs_step_locals
# if undefined define __bs_step_locals as empty dict
if not "__bs_step_locals" in globals():
    __bs_step_locals = {{}}
# load locals from __bs_step_locals
__bs_step_locals['event'] = event
exec(__bs_cell_code_contents[{cell_number}] + "__bs_step_locals = locals()\\ndel __bs_step_locals['__bs_step_locals']",globals(), __bs_step_locals)
return __bs_step_locals['event']
"""

                    parsed_code = ast.parse(clean_code)

                    # Step 3: Create a new function definition
                    new_function = ast.FunctionDef(
                        name=f"step_{cell_number}_internal",
                        args=ast.arguments(
                            posonlyargs=[],
                            args=[ast.arg(arg="event", annotation=None)],
                            kwonlyargs=[],
                            kw_defaults=[],
                            defaults=[],
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
            except Exception:
                print(f"Error in cell: {cell_number}\n{clean_code}")
                # print traceback
                import traceback

                traceback.print_exc()


def main():
    app = App()  # noqa: F405
    if app.Test:
        bspump.jupyter.bitswan_test_mode.append(True)

    if os.path.exists(app.Notebook):
        with open(app.Notebook) as nb:
            notebook = json.load(nb)
            cell_number = 0
            for cell in notebook["cells"]:
                cell_number += 1
                exec_cell(cell, cell_number, globals())
    else:
        print(f"Notebook {app.Notebook} not found")

    if bspump.jupyter.bitswan_auto_pipeline.get("sink") is not None:
        register_sink(bspump.jupyter.bitswan_auto_pipeline.get("sink"))  # noqa: F405
        end_pipeline()  # noqa: F405

    app.init_componets()
    app.run()


if __name__ == "__main__":
    main()
